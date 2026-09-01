## How it works

This design implements the digital readout electronics for a fiber-optic gyroscope (IFOG) using an open-loop lock-in demodulator architecture.

A configurable square-wave modulator (`mod_ref_gen`) generates the phase modulation reference signal, which drives an external phase modulator via `uo_out[0]`. The returning interferometer signal is digitized by an external 1-bit Delta-Sigma ADC and fed into `ui_in[0]`.

The lock-in demodulator (`lockin_demod`) correlates the incoming Delta-Sigma bitstream with the modulation reference, accumulating the result over each modulation cycle. The 16-bit signed output (`demod_out`) represents the measured rotation rate.

An SPI slave interface (`spi_slave`) provides register access:
- **Reg 0**: Modulation period (read/write)
- **Reg 1**: Demodulator output (read-only)

Protocol: 3-byte SPI transfer (Command/Address, Data-High, Data-Low).

## How to test

1. Apply a clock to `clk` and assert `rst_n` (active-low reset).
2. Set `ui_in[1]` (Enable) high to activate the design.
3. Feed a 1-bit Delta-Sigma stream into `ui_in[0]`.
4. Observe the square-wave modulation reference on `uo_out[0]`.
5. The heartbeat LED on `uo_out[2]` toggles at approximately 1 Hz when the design is running.
6. Use SPI to read the demodulated result:
   - Assert `CS_N` (active low)
   - Send 3 bytes: Command (0x01 = read Reg 1), then two dummy bytes
   - Capture MISO during bytes 2 and 3 for the 16-bit `demod_out`

## External hardware

- External 1-bit Delta-Sigma ADC (photodiode frontend)
- External phase modulator (driven by `uo_out[0]`)
- SPI master (microcontroller or FPGA) for register readout
