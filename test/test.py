import cocotb
from cocotb.clock import Clock
from cocotb.triggers import ClockCycles, RisingEdge, FallingEdge, Timer

# ---------------------------------------------------------------------------
# Helper: SPI transfer (Mode 0: CPOL=0, CPHA=0)
# ---------------------------------------------------------------------------
async def spi_transfer(dut, cmd_byte, data_high=0x00, data_low=0x00):
    """
    Sendet 3 Bytes über SPI an den Slave.
    cmd_byte: Bit7=rd(1)/wr(0), Bit0=reg_addr
    Gibt bei Read die 16 empfangenen MISO-Bits zurück, sonst None.

    SPI Mode 0: Der Slave legt MISO nach der fallenden SCK-Flanke um,
    der Master sampled daher am ENDE der Low-Phase (vor der steigenden
    Flanke). MOSI wird während der Low-Phase gewechselt.

    Hinweis: uio_in wird über eine Schattenvariable geführt, weil unter
    cocotb 2.x ein sofortiges Read-back nach einem Write noch den
    alten (abgesetzten) Wert liefert -- Read-modify-write auf
    dut.uio_in.value würde frühere Bitänderungen verwerfen.
    """
    sck_half_period = 500  # ns -> 1 MHz SPI bei 100ns Systemtakt

    uio = 0x08  # Schattenstand: CS_N=1, SCK=0, MOSI=0

    # CS low
    uio &= ~(1 << 3)
    dut.uio_in.value = uio
    await Timer(sck_half_period * 2, units="ns")

    tx_bytes = [cmd_byte, data_high, data_low]
    rx_bits = []

    for byte in tx_bytes:
        for bit in range(7, -1, -1):
            # MOSI setzen (SCK ist low)
            uio = (uio & ~(1 << 1)) | (((byte >> bit) & 1) << 1)
            dut.uio_in.value = uio
            await Timer(sck_half_period, units="ns")

            # MISO samplen: vor der steigenden SCK-Flanke (Mode 0)
            miso_val = (int(dut.uio_out.value) >> 2) & 1
            rx_bits.append(miso_val)

            # SCK high
            uio |= (1 << 0)
            dut.uio_in.value = uio
            await Timer(sck_half_period, units="ns")

            # SCK low
            uio &= ~(1 << 0)
            dut.uio_in.value = uio

    # CS high
    uio |= (1 << 3)
    dut.uio_in.value = uio
    await Timer(sck_half_period * 2, units="ns")

    # Wenn Read (Bit7=1), Bytes 2+3 enthalten die 16 MISO-Bits
    if (cmd_byte >> 7) & 1:
        rx_word = 0
        for i in range(16):
            rx_word = (rx_word << 1) | rx_bits[8 + i]
        return rx_word
    return None


async def wait_rising_bit(dut, bit):
    """
    Wartet auf die steigende Flanke von uo_out[bit] (gepollt an der
    fallenden Taktflanke, damit keine Read-Races mit dem RTL entstehen).
    Ersetzt RisingEdge(dut.uo_out[bit]), das unter cocotb 2.x für
    gepackte Vektoren nicht erlaubt ist.
    Kehrt an der fallenden Taktflanke innerhalb des Pulses zurück.
    """
    prev = (int(dut.uo_out.value) >> bit) & 1
    while True:
        await FallingEdge(dut.clk)
        cur = (int(dut.uo_out.value) >> bit) & 1
        if prev == 0 and cur == 1:
            return
        prev = cur


async def setup_dut(dut, ui=0x02):
    """Gemeinsames Setup: Takt starten, Reset, Enable."""
    clock = Clock(dut.clk, 100, units="ns")  # 10 MHz
    cocotb.start_soon(clock.start())
    dut.ena.value = 1
    dut.ui_in.value = ui
    dut.uio_in.value = 0x08  # CS_N high
    dut.rst_n.value = 0
    await ClockCycles(dut.clk, 5)
    dut.rst_n.value = 1
    await ClockCycles(dut.clk, 10)


# ---------------------------------------------------------------------------
# Fenster-Modell (wichtig für alle Demodulator-Tests)
# ---------------------------------------------------------------------------
# mod_ref_gen: Zähler-Wrap an Takten E0, E(P), E(2P), ... (P = Periode);
# window_done ist jeweils im Zyklus NACH dem Wrap high.
# lockin_demod wertet window_done am Takt ab: Demodulator-Fenster =
# Samples E1..E(P), gelatcht an E(P+1) -- und der Latch passiert nur,
# wenn enable=1 ist. Zum Auslesen per SPI (dauert ~25 us >> Fenster)
# daher: einen Takt nach dem window_done-Puls enable=0 setzen, dann
# bleibt demod_out eingefroren.
# ---------------------------------------------------------------------------


# ---------------------------------------------------------------------------
# Test 1: Reset und Grundzustand
# ---------------------------------------------------------------------------
@cocotb.test()
async def test_reset(dut):
    """Prüft, ob Reset korrekt alle Ausgänge auf definierte Werte setzt."""
    clock = Clock(dut.clk, 100, units="ns")
    cocotb.start_soon(clock.start())

    dut.ena.value = 1
    dut.ui_in.value = 0x00
    dut.uio_in.value = 0x08  # CS_N high
    dut.rst_n.value = 0

    await ClockCycles(dut.clk, 10)
    dut.rst_n.value = 1
    await ClockCycles(dut.clk, 5)

    # Nach Reset sollte ref_sign = 0, window_done = 0
    assert dut.uo_out.value[0] == 0, "ref_sign sollte nach Reset 0 sein"
    assert dut.uo_out.value[1] == 0, "window_done sollte nach Reset 0 sein"
    dut._log.info("Reset-Test bestanden")


# ---------------------------------------------------------------------------
# Test 2: Heartbeat-LED
# ---------------------------------------------------------------------------
@cocotb.test()
async def test_heartbeat(dut):
    """
    Prüft den Heartbeat-Zähler. Ein voller Toggle dauert 5 Mio. Zyklen
    (~0.5 s bei 10 MHz), darum wird hier nur verifiziert, dass die LED
    nach 2000 Zyklen noch stabil ist (kein versehentliches Toggeln).
    """
    await setup_dut(dut)

    initial_led = (int(dut.uo_out.value) >> 2) & 1
    await ClockCycles(dut.clk, 2000)
    assert ((int(dut.uo_out.value) >> 2) & 1) == initial_led, \
        "Heartbeat sollte nach 2000 Zyklen noch nicht toggeln"
    dut._log.info("Heartbeat-Test bestanden (Zähler läuft)")


# ---------------------------------------------------------------------------
# Test 3: Modulationsreferenz-Periode
# ---------------------------------------------------------------------------
@cocotb.test()
async def test_modulation_period(dut):
    """Prüft, ob die Modulationsreferenz mit der per SPI gesetzten Periode toggelt."""
    await setup_dut(dut)

    # Setze Modulationsperiode auf 20 über SPI (Write Reg 0)
    await spi_transfer(dut, cmd_byte=0x00, data_high=0x00, data_low=0x14)
    await ClockCycles(dut.clk, 5)

    # Warte auf window_done-Pulse und messe deren Abstand
    await wait_rising_bit(dut, 1)
    start_time = cocotb.utils.get_sim_time("ns")

    await wait_rising_bit(dut, 1)
    end_time = cocotb.utils.get_sim_time("ns")

    period_ns = end_time - start_time
    expected_ns = 20 * 100  # 20 Zyklen * 100 ns

    assert abs(period_ns - expected_ns) <= 200, \
        f"Modulationsperiode falsch: {period_ns}ns, erwartet ~{expected_ns}ns"

    dut._log.info(f"Modulationsperiode korrekt: {period_ns}ns (erwartet {expected_ns}ns)")


# ---------------------------------------------------------------------------
# Test 4: SPI Write + Readback
# ---------------------------------------------------------------------------
@cocotb.test()
async def test_spi_write_read(dut):
    """Schreibt einen Wert in Reg 0 und liest ihn zurück."""
    await setup_dut(dut)

    # Schreibe 0xABCD in Reg 0
    await spi_transfer(dut, cmd_byte=0x00, data_high=0xAB, data_low=0xCD)
    await ClockCycles(dut.clk, 5)

    # Lese Reg 0 zurück (cmd = 0x80, da Bit7=1, Bit0=0)
    rx_data = await spi_transfer(dut, cmd_byte=0x80, data_high=0x00, data_low=0x00)

    assert rx_data == 0xABCD, f"SPI Readback fehlgeschlagen: {rx_data:04X} != ABCD"
    dut._log.info(f"SPI Readback korrekt: 0x{rx_data:04X}")


# ---------------------------------------------------------------------------
# Test 5: Lock-in Demodulator mit simuliertem Delta-Sigma (Smoke-Test)
# ---------------------------------------------------------------------------
@cocotb.test()
async def test_lockin_demod(dut):
    """
    Füttert konstant ds_bit = 1 in den Demodulator. Da ref_sign innerhalb
    eines Fensters konstant ist, muss jede volle Fenster-Akkumulation
    exakt +/-Periode ergeben (Vollausschlag, Vorzeichen je nach Phase).
    """
    await setup_dut(dut)

    # Setze kurze Periode für schnellen Test
    await spi_transfer(dut, cmd_byte=0x00, data_high=0x00, data_low=0x10)  # Periode = 16

    # ds_bit = 1 konstant anlegen, BEVOR das Referenzfenster startet
    dut.ui_in.value = 0x03  # enable=1, ds_bit=1

    # Zwei Fenstergrenzen abwarten -> dazwischen liegt ein volles
    # Fenster mit ds_bit = 1
    await wait_rising_bit(dut, 1)
    await wait_rising_bit(dut, 1)
    await ClockCycles(dut.clk, 1)  # Latch-Takt (E(P+1)) mit enable=1 durchlassen

    # Demodulator einfrieren: bei enable=0 haelt demod_out seinen Wert,
    # sonst laeuft waehrend der SPI-Uebertragung (~25 us) schon das
    # naechste Fenster ueber und das Register aendert sich unterwegs.
    dut.ui_in.value = 0x00
    await ClockCycles(dut.clk, 2)

    # Lese demod_out aus Reg 1
    rx_data = await spi_transfer(dut, cmd_byte=0x81, data_high=0x00, data_low=0x00)
    signed_val = rx_data if rx_data < 32768 else rx_data - 65536
    dut._log.info(f"Demodulator-Output: 0x{rx_data:04X} (signed: {signed_val})")

    assert abs(signed_val) == 16, \
        f"|demod_out| sollte 16 (= Periode, Vollausschlag) sein, war {signed_val}"
    dut._log.info("Lock-in Demodulator-Test bestanden")


# ---------------------------------------------------------------------------
# Test 6: SPI Demodulator-Readout nach simuliertem Input
# ---------------------------------------------------------------------------
@cocotb.test()
async def test_spi_full_readout(dut):
    """
    Vollständiger Test: Setze Periode, füttere Delta-Sigma, warte auf
    window_done, lese Ergebnis per SPI.
    """
    await setup_dut(dut)

    # Periode = 32
    await spi_transfer(dut, cmd_byte=0x00, data_high=0x00, data_low=0x20)

    # Warte auf Fenstergrenze (Rückkehr: fallende Flanke F0 im Puls)
    await wait_rising_bit(dut, 1)
    ref_new = int(dut.uo_out.value) & 1

    # Erzeuge ein Muster: ds_bit = ref_sign für 24 Zyklen, dann ds_bit != ref_sign.
    # Samples E2..E32 (31 Stück, gesteuert); Sample E1 läuft noch mit ds=0.
    for i in range(31):
        await FallingEdge(dut.clk)
        ref = int(dut.uo_out.value) & 1
        ds = ref if i < 24 else (1 - ref)
        dut.ui_in.value = 0x02 | ds

    # Fenster W = E1..E32: E1 mit ds=0 -> corr = +1 gdw. ref_new==0;
    # E2..E25: 24x Match, E26..E32: 7x Mismatch -> +17
    expected = 17 + (1 if ref_new == 0 else -1)

    # Warte auf Fensterende-Puls, dann Latch-Takt abwarten und einfrieren
    await wait_rising_bit(dut, 1)
    await ClockCycles(dut.clk, 1)  # Latch-Takt mit enable=1 durchlassen
    dut.ui_in.value = 0x00
    await ClockCycles(dut.clk, 3)

    # Lese Reg 1 (demod_out)
    rx_data = await spi_transfer(dut, cmd_byte=0x81, data_high=0x00, data_low=0x00)

    signed_val = rx_data if rx_data < 32768 else rx_data - 65536
    dut._log.info(f"SPI Readout: 0x{rx_data:04X} = {signed_val} (signed), erwartet {expected}")

    assert signed_val == expected, \
        f"demod_out = {signed_val}, erwartet {expected}"
    dut._log.info("SPI Full-Readout-Test bestanden")


# ---------------------------------------------------------------------------
# Test 7: Numerischer Readout-Test (Erwartwert exakt mitverfolgt)
# ---------------------------------------------------------------------------
@cocotb.test()
async def test_spi_numeric_readout(dut):
    """
    Numerischer Test: demod_out muss exakt dem berechneten Erwartwert
    entsprechen.

    Fenster W = E1..E32 (Periode 32, siehe Fenster-Modell oben).
    Alle 32 Samples werden gesteuert: 24x ds == ref (corr = +1),
    8x ds != ref (corr = -1) -> Erwartwert = 24 - 8 = +16.
    """
    await setup_dut(dut, ui=0x02)

    # Periode = 32 Takte
    await spi_transfer(dut, cmd_byte=0x00, data_high=0x00, data_low=0x20)

    # Warte auf Fenstergrenze (Rückkehr: fallende Flanke F0 im Puls-Zyklus)
    await wait_rising_bit(dut, 1)
    ref_new = int(dut.uo_out.value) & 1

    # Samples E1..E31: 24x Match, 7x Mismatch. Sample E32 übernimmt den
    # letzten gesetzten Wert (Mismatch) -> insgesamt 24 - 8 = +16.
    expected = 0
    for i in range(31):
        ref = int(dut.uo_out.value) & 1
        assert ref == ref_new, "ref_sign hat innerhalb des Fensters gewechselt"
        ds = ref if i < 24 else (1 - ref)
        dut.ui_in.value = 0x02 | ds
        expected += 1 if ds == ref else -1
        await RisingEdge(dut.clk)       # Sample-Edge E(i+1)
        if i < 30:
            await FallingEdge(dut.clk)  # zurück zur Mitte des Zyklus
    expected -= 1  # Sample E32: ds vom letzten Loop-Durchlauf (Mismatch)

    # Fensterende-Puls abwarten, Latch-Takt E33 mit enable=1 durchlassen,
    # dann einfrieren (enable=0 haelt demod_out), damit sich das Register
    # waehrend der ~25 us langen SPI-Uebertragung nicht mehr aendert.
    await wait_rising_bit(dut, 1)
    await ClockCycles(dut.clk, 1)
    dut.ui_in.value = 0x00
    await ClockCycles(dut.clk, 3)

    rx_data = await spi_transfer(dut, cmd_byte=0x81, data_high=0x00, data_low=0x00)
    rx_signed = rx_data if rx_data < 32768 else rx_data - 65536
    dut._log.info(f"Numerischer Readout: {rx_signed} (erwartet {expected})")

    assert rx_signed == expected, \
        f"demod_out = {rx_signed}, erwartet {expected}"
    assert expected == 16, "Testdesign-Fehler: Erwartwert muss 16 sein"
    dut._log.info("Numerischer Readout-Test bestanden")
