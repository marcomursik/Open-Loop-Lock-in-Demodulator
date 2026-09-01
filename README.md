![](../../workflows/gds/badge.svg) ![](../../workflows/docs/badge.svg) ![](../../workflows/test/badge.svg)

# Laser Gyro Lock-in Readout Core

Open-loop lock-in demodulator for the digital readout electronics of a
single-axis laser gyroscope (fiber-optic interferometer), targeting the
Tiny Tapeout shuttle **TTIHP26b** (IHP SG13G2, 130 nm).

Author: Marco Flückiger

## How it works

```
1-bit ΔΣ bitstream (photodiode frontend)
        │
        ▼   ui_in[0]          ui_in[1] = Enable
┌───────────────────────────────────────────────┐
│              tt_um_gyro_lockin                │
│                                               │
│  mod_ref_gen ──► lockin_demod ──► spi_slave   │
│  (square-wave     (correlator +   (register   │
│   reference)       accumulator)    interface) │
│       │                                  │    │
│       ▼ uo_out[0] (to piezo              ▼    │
│          phase modulator)           SPI SCK/  │
│       uo_out[1] window_done         MOSI/MISO/│
│       uo_out[2] heartbeat LED       CS_N      │
└───────────────────────────────────────────────┘
```

A configurable square-wave generator (`mod_ref_gen`) produces the phase
modulation reference that drives an external fiber-optic phase modulator
(e.g. a low-cost piezo fiber stretcher) via `uo_out[0]`. The returning
interferometer signal is digitized by an external 1-bit delta-sigma ADC
and fed into `ui_in[0]`. The lock-in demodulator (`lockin_demod`)
correlates the bitstream with the modulation reference and accumulates
over each modulation half-cycle; the 16-bit signed result is read over
SPI (`spi_slave`, mode 0).

- [Full design documentation](docs/info.md)
- [Hardware setup (piezo build) and calculations](docs/hardware.md)

## Register map (SPI, 3-byte transfers)

| Addr | Register | Access | Description |
|------|----------|--------|-------------|
| 0 | `mod_period` | R/W | Modulation half-period in clock cycles (default 1000) |
| 1 | `demod_out` | R | Demodulator output, signed 16-bit (saturating) |

Command byte: bit 7 = read(1)/write(0), bit 0 = address.
Examples: `0x00 0x03 0xE8` → set period to 1000 · `0x81 0x00 0x00` →
read `demod_out` (MISO during bytes 2–3, MSB first).

## Testing

The cocotb testbench in `test/` covers reset, heartbeat, modulation
period, SPI write/readback, lock-in accumulation and an exact numeric
readout check (7/7 passing with Icarus Verilog + cocotb 2.0.1):

```bash
cd test
pip install -r requirements.txt
make
```

## Submission

Shuttle TTIHP26b, 1x1 tile, top module `tt_um_gyro_lockin`.
Submit via [app.tinytapeout.com](https://app.tinytapeout.com/projects/create).

## What is Tiny Tapeout?

Tiny Tapeout is an educational project that aims to make it easier and
cheaper than ever to get your digital designs manufactured on a real chip.
Learn more at https://tinytapeout.com.

## Resources

- [FAQ](https://tinytapeout.com/faq/)
- [Digital design lessons](https://tinytapeout.com/digital_design/)
- [Join the community](https://tinytapeout.com/discord)
