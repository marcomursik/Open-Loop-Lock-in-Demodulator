`default_nettype none

module lockin_demod #(
    parameter ACC_BITS = 24
)(
    input  wire clk,
    input  wire rst_n,
    input  wire enable,
    input  wire ds_bit,
    input  wire ref_sign,
    input  wire window_done,
    output reg  signed [15:0] demod_out,
    output reg  valid
);

    reg signed [ACC_BITS-1:0] acc;

    // Correlation: +1 if ds_bit == ref_sign, -1 otherwise
    wire signed [1:0] corr = (ds_bit == ref_sign) ? 2'sd1 : -2'sd1;

    always @(posedge clk or negedge rst_n) begin
        if (!rst_n) begin
            acc       <= 0;
            demod_out <= 0;
            valid     <= 0;
        end else if (enable) begin
            if (window_done) begin
                demod_out <= acc >>> 8;  // Placeholder scaling
                acc       <= corr;
                valid     <= 1'b1;
            end else begin
                acc   <= acc + corr;
                valid <= 1'b0;
            end
        end else begin
            valid <= 1'b0;
        end
    end

endmodule
