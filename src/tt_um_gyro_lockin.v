`default_nettype none

module tt_um_gyro_lockin (
    input  wire [7:0] ui_in,
    output wire [7:0] uo_out,
    input  wire [7:0] uio_in,
    output wire [7:0] uio_out,
    output wire [7:0] uio_oe,
    input  wire       ena,
    input  wire       clk,
    input  wire       rst_n
);

    // Enable signal
    wire enable = ui_in[1];

    // Modulation period register (configurable via SPI)
    reg [15:0] mod_period;
    wire [15:0] spi_wdata;
    wire        spi_wr;
    wire [0:0]  spi_addr;

    // Demodulator output
    wire signed [15:0] demod_out;
    wire               demod_valid;

    // Modulation reference
    wire ref_sign;
    wire window_done;

    // SPI signals
    wire sck  = uio_in[0];
    wire mosi = uio_in[1];
    wire cs_n = uio_in[3];
    wire miso;

    // Heartbeat LED (~1 Hz at 10 MHz = 5_000_000 cycles)
    reg [23:0] hb_cnt;
    reg        hb_led;

    always @(posedge clk or negedge rst_n) begin
        if (!rst_n) begin
            hb_cnt  <= 0;
            hb_led  <= 0;
        end else if (enable) begin
            if (hb_cnt >= 24'd5_000_000) begin
                hb_cnt <= 0;
                hb_led <= ~hb_led;
            end else begin
                hb_cnt <= hb_cnt + 1;
            end
        end
    end

    // SPI register write
    always @(posedge clk or negedge rst_n) begin
        if (!rst_n) begin
            mod_period <= 16'd1000; // Default period
        end else if (spi_wr && spi_addr == 0) begin
            mod_period <= spi_wdata;
        end
    end

    // Module instantiations
    mod_ref_gen #(
        .PERIOD_BITS(16)
    ) mod_gen (
        .clk         (clk),
        .rst_n       (rst_n),
        .enable      (enable),
        .period      (mod_period),
        .ref_sign    (ref_sign),
        .window_done (window_done)
    );

    lockin_demod #(
        .ACC_BITS(24)
    ) demod (
        .clk         (clk),
        .rst_n       (rst_n),
        .enable      (enable),
        .ds_bit      (ui_in[0]),
        .ref_sign    (ref_sign),
        .window_done (window_done),
        .demod_out   (demod_out),
        .valid       (demod_valid)
    );

    spi_slave spi (
        .clk        (clk),
        .rst_n      (rst_n),
        .sck        (sck),
        .mosi       (mosi),
        .miso       (miso),
        .cs_n       (cs_n),
        .reg_wdata  (spi_wdata),
        .reg_wr     (spi_wr),
        .reg_addr   (spi_addr),
        .reg_rdata_0(mod_period),
        .reg_rdata_1(demod_out)
    );

    // Output assignments
    assign uo_out[0]   = ref_sign;
    assign uo_out[1]   = window_done;
    assign uo_out[2]   = hb_led;
    assign uo_out[7:3] = 5'b0;

    assign uio_out[0]  = 1'b0;
    assign uio_out[1]  = 1'b0;
    assign uio_out[2]  = miso;
    assign uio_out[7:3]= 5'b0;

    assign uio_oe = 8'b0000_0100; // Only MISO (uio[2]) is output

    // Unused inputs (prevents synthesis warnings)
    wire _unused = &{ena, uio_in[7:4], uio_in[2], ui_in[7:2], demod_valid, 1'b0};

endmodule
