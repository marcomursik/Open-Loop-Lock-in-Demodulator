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
                    rd_flag  <= rx_sr[7];
                    reg_addr <= rx_sr[0];
                    if (rx_sr[7]) begin
                        tx_sr <= (rx_sr[0] == 0) ? reg_rdata_0 : reg_rdata_1;
                    end
                end else if (bit_cnt == 5'd15) begin
                    if (!rd_flag) begin
                        reg_wdata[15:8] <= {rx_sr[14:8], mosi};
                    end
                end else if (bit_cnt == 5'd23) begin
                    bit_cnt <= 0;
                    if (!rd_flag) begin
                        reg_wdata[7:0] <= {rx_sr[22:16], mosi};
                        reg_wr <= 1;
                    end
                    rd_flag <= 0;
                end
            end
        end
    end

    assign miso = cs_active && rd_flag ? tx_sr[15] : 1'b0;

endmodule
