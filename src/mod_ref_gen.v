`default_nettype none

module mod_ref_gen #(
    parameter PERIOD_BITS = 16
)(
    input  wire clk,
    input  wire rst_n,
    input  wire enable,
    input  wire [PERIOD_BITS-1:0] period,
    output reg  ref_sign,
    output reg  window_done
);

    reg [PERIOD_BITS-1:0] counter;

    always @(posedge clk or negedge rst_n) begin
        if (!rst_n) begin
            counter     <= 0;
            ref_sign    <= 0;
            window_done <= 0;
        end else if (enable) begin
            if (counter >= period - 1'b1) begin
                counter     <= 0;
                ref_sign    <= ~ref_sign;
                window_done <= 1'b1;
            end else begin
                counter     <= counter + 1'b1;
                window_done <= 1'b0;
            end
        end else begin
            window_done <= 1'b0;
        end
    end

endmodule
