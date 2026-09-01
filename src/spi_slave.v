`default_nettype none

module spi_slave (
    input  wire clk,
    input  wire rst_n,
    input  wire sck,
    input  wire mosi,
    output wire miso,
    input  wire cs_n,

    output reg  [15:0] reg_wdata,
    output reg         reg_wr,
    output reg  [0:0]  reg_addr,
    input  wire [15:0] reg_rdata_0,
    input  wire [15:0] reg_rdata_1
);

    // 2-FF synchronizers
    reg [2:0] sck_sync;
    reg [2:0] cs_sync;
    wire sck_rising = (sck_sync[2:1] == 2'b01);
    wire cs_active  = !cs_sync[2];

    always @(posedge clk or negedge rst_n) begin
        if (!rst_n) begin
            sck_sync <= 3'b000;
            cs_sync  <= 3'b111;
        end else begin
            sck_sync <= {sck_sync[1:0], sck};
            cs_sync  <= {cs_sync[1:0], cs_n};
        end
    end

    reg [4:0]  bit_cnt;
    reg [23:0] rx_sr;
    reg [15:0] tx_sr;
    reg        rd_flag;

    always @(posedge clk or negedge rst_n) begin
        if (!rst_n) begin
            bit_cnt  <= 0;
            rx_sr    <= 0;
            tx_sr    <= 0;
            reg_wr   <= 0;
            reg_addr <= 0;
            reg_wdata<= 0;
            rd_flag  <= 0;
        end else begin
            reg_wr <= 0;

            if (!cs_active) begin
                bit_cnt <= 0;
                rd_flag <= 0;
            end else if (sck_rising) begin
                rx_sr <= {rx_sr[22:0], mosi};
                bit_cnt <= bit_cnt + 1'b1;

                if (rd_flag) begin
                    tx_sr <= {tx_sr[14:0], 1'b0};
                end

                if (bit_cnt == 5'd7) begin
                    // Nonblocking semantics: at the 8th SCK edge rx_sr holds
                    // only the first 7 command bits (cmd[7:1] in rx_sr[6:0]),
                    // the last command bit (cmd[0]) is still on the mosi pin.
                    rd_flag  <= rx_sr[6];   // cmd[7]: 1 = read, 0 = write
                    reg_addr <= mosi;       // cmd[0]: register address
                    if (rx_sr[6]) begin
                        tx_sr <= mosi ? reg_rdata_1 : reg_rdata_0;
                    end
                end else if (bit_cnt == 5'd15) begin
                    // rx_sr is a left-shifting register: at each byte boundary
                    // the last 8 stream bits are in {rx_sr[6:0], mosi}.
                    if (!rd_flag) begin
                        reg_wdata[15:8] <= {rx_sr[6:0], mosi};  // data-high byte
                    end
                end else if (bit_cnt == 5'd23) begin
                    bit_cnt <= 0;
                    if (!rd_flag) begin
                        reg_wdata[7:0] <= {rx_sr[6:0], mosi};   // data-low byte
                        reg_wr <= 1;
                    end
                    rd_flag <= 0;
                end
            end
        end
    end

    assign miso = cs_active && rd_flag ? tx_sr[15] : 1'b0;

endmodule
