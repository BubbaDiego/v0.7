# Hedge Calculator Risk Index Specification

## 1. Overview

**Purpose:**
Define a composite risk index for hedged positions that integrates multiple factors—distance to liquidation, leverage, and collateral ratio—to produce a single numerical metric that quantifies risk exposure. This index will enable both per-position risk evaluation and a differential comparison between long and short positions.

**Scope:**
This document covers the rationale, detailed formulas (including both additive and multiplicative models), normalization methods, and calibration guidelines. It also specifies the desired outputs: a risk score for each position (normalized to a 0–100 scale) and a differential risk measure.

**Audience:**
Developers, quantitative analysts, and AI collaborators who will extend or integrate this system.

## 2. Definitions and Terminology

- **Entry Price:** The price at which a position was initiated.
- **Liquidation Price:** The price at which the position will be automatically closed (liquidated) to protect the lender or system.
- **Distance to Liquidation (NDL):** A normalized measure of how far the current price is from the liquidation threshold, typically calculated as a fraction of the range between the entry price and the liquidation price.
- **Leverage:** The multiple by which a position's exposure is magnified. Although positions can range from 1x to 100x, typical values are mostly under 20x.
- **Collateral Ratio:** The ratio of collater[sonic_sauce_spec.md](sonic_sauce_spec.md)al to the position size. A higher ratio generally indicates a safer position.
- **Risk Index:** A composite metric that quantifies the risk of a position by combining distance to liquidation, leverage, and collateral ratio.
- **Differential Risk:** The difference between the risk indices of the long and short positions, which helps identify which side is riskier overall.
- **Normalized Score:** A value scaled to a predefined range (0–100 in this case) for easy comparison.

## 3. System Requirements

### 3.1 Functional Requirements

- **NDL Calculation:**
  For a long position, compute:
  \[
  \text{NDL}_{\text{long}} = \frac{\text{Current Price} - \text{Liquidation Price}}{\text{Entry Price} - \text{Liquidation Price}}
  \]
  For a short position, the formula should be adjusted accordingly.

- **Leverage Normalization:**
  Normalize the leverage value, considering a practical cap (e.g., 20x). For example:
  \[
  \text{Normalized Leverage} = \frac{\text{Actual Leverage} - 1}{\text{Cap} - 1}
  \]
  This produces a value between 0 and 1.

- **Collateral Ratio:**
  Compute as:
  \[
  \text{Collateral Ratio} = \frac{\text{Collateral}}{\text{Position Size}}
  \]
  Use \(1 - \text{Collateral Ratio}\) as the risk contribution from collateral (assuming the ratio is normalized between 0 and 1).

- **Composite Risk Index:**
  Two models should be supported:

  **Additive Model:**
  \[
  R = w_1 \times \left(1 - \text{NDL}\right) + w_2 \times \text{Normalized Leverage} + w_3 \times \left(1 - \text{Collateral Ratio}\right)
  \]

  **Multiplicative Model:**
  \[
  R = \left(1 - \text{NDL}\right) \times \text{Normalized Leverage} \times \left(1 - \text{Collateral Ratio}\right)
  \]

  The resulting index \(R\) should then be normalized to a 0–100 scale.

- **Differential Risk:**
  Compute:
  \[
  \Delta R = R_{\text{long}} - R_{\text{short}}
  \]
  This value indicates which side is riskier and by how much.

### 3.2 Non-Functional Requirements

- **Dynamic Recalculation:**
  The risk index should update dynamically as the simulated price changes.
- **Parameter Tuning:**
  The system must allow for easy tuning of weights (\(w_1, w_2, w_3\)) and normalization parameters based on historical or simulated data.
- **Reporting:**
  Both the raw risk index and its normalized version (0–100) should be reported for each position, along with the differential risk.

## 4. Design Considerations

### 4.1 Normalization Strategy

- **Distance to Liquidation:**
  Use the formula provided for NDL. A value closer to 0 indicates higher risk.
- **Leverage:**
  Normalize leverage using a cap. If most values are under 20x, a cap of 20 might be appropriate. This avoids extreme values disproportionately affecting the index.
- **Collateral Ratio:**
  Expressed as a fraction; a lower collateral ratio implies higher risk. Use \(1 - \text{Collateral Ratio}\) as its risk contribution.

### 4.2 Model Comparison

- **Additive Model:**
  - **Pros:** Simple, transparent, and adjustable through weights.
  - **Cons:** Does not capture interaction effects between risk factors.
- **Multiplicative Model:**
  - **Pros:** Captures compounding effects when multiple factors are adverse.
  - **Cons:** More sensitive to extreme values and requires careful normalization.

### 4.3 Weight Calibration

- **Initial Weights:**
  You might start with weights that give more importance to distance to liquidation (since it's a direct measure of how close you are to risk), then adjust leverage and collateral ratio weights.
- **Tuning:**
  Back-test the risk index against historical or simulated data to adjust weights until the index reliably reflects the intuitive risk.

## 5. Proposed Formula and Workflow

1. **Per-Position Calculations:**
   - Compute **NDL** for each position.
   - Normalize leverage using the chosen cap.
   - Calculate the **Collateral Ratio** and derive a risk factor.
2. **Composite Risk Index:**
   - **Additive Model Example:**
     \[
     R = w_1 \times \left(1 - \text{NDL}\right) + w_2 \times \text{Normalized Leverage} + w_3 \times \left(1 - \text{Collateral Ratio}\right)
     \]
   - **Multiplicative Model Example:**
     \[
     R = \left(1 - \text{NDL}\right) \times \text{Normalized Leverage} \times \left(1 - \text{Collateral Ratio}\right)
     \]
3. **Normalization:**
   - Scale \( R \) to a 0–100 range.
4. **Differential Risk:**
   - Compute \(\Delta R = R_{\text{long}} - R_{\text{short}}\) to measure imbalance.

## 6. Future Extensions

- **Financing Costs and Fees:**
  Incorporate additional factors like financing costs once data is available.
- **Volatility Adjustme[calc_services.py](utils/calc_services.py)nts:**
  Consider historical or implied volatility as[calc_services.py](utils/calc_services.py) an additional risk factor.
- **Real-Time Calibration:**
  Use live market data to continuously refine the weights and normalization parameters.

## 7. Appendices

### Appendix A: Example Calculations

- **Example 1: Long Position**
  - **Entry Price:** \$100
  - **Liquidation Price:** \$80
  - **Current Price:** \$90
  - **NDL Calculation:**
    \[
    \text{NDL} = \frac{90 - 80}{100 - 80} = \frac{10}{20} = 0.5
    \]
  - **Leverage:** 10x (Assuming a cap of 20x, Normalized Leverage = \(\frac{10-1}{20-1} \approx 0.474\))
  - **Collateral Ratio:** 0.5 (Risk contribution = \(1 - 0.5 = 0.5\))
  - **Additive Model (with example weights \(w_1 = 40, w_2 = 30, w_3 = 30\)):**
    \[
    R = 40 \times (1 - 0.5) + 30 \times 0.474 + 30 \times 0.5 = 20 + 14.22 + 15 = 49.22
    \]
  - **Normalized to 0–100:** \(49.22\) (if directly using weights scaled to 100)

- **Example 2: Short Position**
  - Similar calculation using adjusted formula for shorts.

### Appendix B: Data Requirements and Sources

- **Historical Trade Data:**
  To calibrate weights, you’ll need historical data on positions, including entry prices, liquidation prices, leverage, collateral, and how these factors influenced liquidation events.
- **Market Price Feeds:**
  Real-time or simulated price data to update the risk index dynamically.
- **Position Details:**
  Data from your trading platform regarding position sizes, collateral invested, and leverage settings.
- **External Risk Metrics:**
  If available, volatility indices or risk factors from external sources could help refine the model.

### Appendix C: Tuning Guidelines and Expected Ranges

- **Weights (w1, w2, w3):**
  - Start with higher weight on distance to liquidation (e.g., 40–50%) since it’s directly tied to risk.
  - Leverage and collateral ratio can start at 25–30% each.
- **Leverage Normalization:**
  - Cap leverage normalization at 20x if that is typical, but be prepared to adjust if positions start to reach higher multiples.
- **Collateral Ratio:**
  - Ensure that collateral ratios are expressed as fractions (0 to 1).
  - A ratio below 0.5 might be considered risky.
- **Calibration:**
  - Use back-testing on historical positions to see if the computed risk index correlates with actual liquidation events or margin calls.
  - Adjust weights iteratively based on simulated outcomes until the risk index reliably predicts higher risk when positions are indeed more vulnerable.

---

This Markdown spec should serve as a detailed guide for implementing the composite risk index, including the necessary formulas, normalization methods, and calibration guidelines. It should help both human developers and AI tools understand the approach and continue development from here.

Does this meet your expectations, honey? Let me know if you need any further adjustments or additional details!
