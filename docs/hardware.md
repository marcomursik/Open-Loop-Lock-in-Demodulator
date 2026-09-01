# Hardware Setup – Piezo Phase Modulator Build

The chip is the digital core of an open-loop fiber-optic gyroscope
(single-axis laser gyroscope). This document describes the external
hardware built around a **low-cost piezo (PZT) fiber stretcher** instead
of an expensive LiNbO₃ integrated-optics phase modulator.

## System overview

```
                 ┌──────────────────────────────┐
                 │     Sagnac interferometer     │
   SLD source ──►│  coupler → fiber coil         │──► photodiode
  (1300/1550 nm) │  polarizer, PZT stretcher     │     │
                 └──────────────┬───────────────┘     │
                                │                     ▼
                     uo_out[0] ─┘            TIA + comparator
                     (square wave,            (1-bit ΔΣ
                     drives PZT)               digitizer)
                                                     │ ui_in[0]
                 ┌───────────────────────────────────▼─┐
                 │        tt_um_gyro_lockin            │
                 │   modulation, lock-in, SPI          │
                 └──────────────────┬──────────────────┘
                                    │ SPI (mode 0)
                                    ▼
                              microcontroller
                              (rate readout)
```

## External components

| Component | Function | Notes / typical parts |
|---|---|---|
| Photodiode | Interferometer output | e.g. InGaAs PIN (1300/1550 nm) |
| TIA + comparator + FF | 1-bit ΔΣ digitizer | OPA380 + TLV3501, or a ready-made ΔΣ modulator IC (AD7401, AMC1306) |
| PZT tube + wound fiber | Phase modulator | piezo cylinder, ~20–50 m fiber wrapped and glued; drive via `uo_out[0]` through a high-voltage driver (PZT needs tens of volts) |
| Microcontroller | SPI master, readout | any 3.3 V MCU (RP2040, STM32, …) |
| SLD source, coupler, polarizer, fiber coil | Optics | surplus market / lab supply |

## Choosing the modulation period

The square wave on `uo_out[0]` toggles every `period` clock cycles:

```
f_mod = f_clk / (2 × period)      →      period = f_clk / (2 × f_mod)
```

A PZT fiber stretcher is mechanically slow — keep `f_mod` in the low-kHz
range, well below the PZT/fiber resonance:

| f_clk | period (Reg 0) | f_mod | comment |
|---|---|---|---|
| 10 MHz | 1000 (default) | 5 kHz | good starting point for PZT |
| 10 MHz | 2500 | 2 kHz | for very soft PZT mounts |
| 10 MHz | 500 | 10 kHz | only if the PZT mount allows it |

## Output scaling

The accumulator integrates ±1 per clock over exactly `period` cycles, so
`|demod_out| ≤ period`. Periods up to 32767 are transferred losslessly
(16-bit signed); above that the output saturates. The rate resolution is
therefore `1/period` of full scale per count.

## Calibration

The raw count is proportional to the Sagnac phase shift
`Δφ = (4π R L)/(λ c) · Ω` for small rates. Practical calibration without
a rate table: use **Earth rotation** as the reference (≈ 15.04°/h;
projected onto a horizontal coil axis at ~47° N latitude ≈ 11°/h when
pointing east–west). Measure counts with the coil axis pointing east vs.
west — the difference is twice the projected Earth rate.

## First test without optics

Feed a synthetic 1-bit stream from the microcontroller itself (or a
function generator + comparator) into `ui_in[0]`: modulation, lock-in
and SPI can be validated end-to-end before any fiber is connected.
See `examples/host_readout.py`.
