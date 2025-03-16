# Hedge Calculator Risk Index Specification (Updated)

## 1. Overview

**Purpose:**  
Define a composite risk index for hedged positions that integrates multiple risk factors—distance to liquidation, leverage, and collateral ratio—into a single numerical metric. This index (often referred to as the "heat index") enables both per-position risk evaluation and differential risk comparison between long and short positions. A higher score (on a 0–100 scale) indicates a higher risk exposure.

**Scope:**  
This document covers the rationale, formulas, normalization methods, error handling, and integration guidelines required to fully recreate the current composite risk index implementation. It documents all input parameters, calculation steps, and UI integration details.

**Audience:**  
Developers, quantitative analysts, and technical integrators who will extend or integrate the Hedge Calculator system.

## 2. Definitions and Terminology

- **Entry Price:** The price at which a position was initiated.
- **Liquidation Price:** The price at which the position will be automatically closed to prevent further losses.
- **Current Price:** The simulated or live price used for risk calculations.
- **Distance to Liquidation (NDL):** A normalized measure of how far the current price is from the liquidation threshold. It is computed as a fraction of the price range between the entry and liquidation prices.
- **Leverage:** The multiple by which a position’s exposure is magnified. While positions can range widely (up to 100x in this implementation), typical values are lower.
- **Normalized Leverage:** In this system, leverage is normalized by dividing the actual leverage by 100.
- **Collateral Ratio:** The ratio of collateral to the position size, capped at 1. A higher ratio indicates a safer position.
- **Risk Contribution from Collateral:** Computed as \(1 - \text{Collateral Ratio}\).
- **Composite Risk Index (Heat Index):** A metric that quantifies the risk of a position by combining the three factors into one score, normalized to a 0–100 range.
- **Differential Risk:** The difference between the risk indices of the long and short positions, highlighting which side is riskier.

## 3. System Requirements

### 3.1 Functional Requirements

1. **Input Data Validation:**  
   - Required fields: `entry_price`, `current_price`, `liquidation_price`, `collateral`, `size`, `leverage`, and `position_type` (either "LONG" or "SHORT").
   - Ensure that `entry_price`, `liquidation_price`, `collateral`, and `size` are greater than 0.
   - Verify that \(|\text{entry_price} - \text{liquidation_price}|\) is sufficiently large (e.g., > 1e-6) to avoid division by zero.

2. **NDL Calculation:**  
   - **For Long Positions:**  
     \[
     \text{NDL} = \frac{\text{current price} - \text{liquidation price}}{\text{entry price} - \text{liquidation price}}
     \]
   - **For Short Positions:**  
     \[
     \text{NDL} = \frac{\text{liquidation price} - \text{current price}}{\text{liquidation price} - \text{entry price}}
     \]
   - Clamp the NDL value to the range \([0, 1]\).

3. **Distance Factor:**  
   - Calculate as:  
     \[
     \text{Distance Factor} = 1 - \text{NDL}
     \]

4. **Leverage Normalization:**  
   - Normalize leverage by dividing the actual leverage by 100:
     \[
     \text{Normalized Leverage} = \frac{\text{leverage}}{100}
     \]
   - This assumes an effective maximum of 100x leverage for scaling purposes.

5. **Collateral Ratio and Risk Contribution:**  
   - Compute collateral ratio:
     \[
     \text{Collateral Ratio} = \frac{\text{collateral}}{\text{position size}}
     \]
   - Cap this ratio at 1.
   - Compute risk contribution from collateral as:
     \[
     \text{Risk Collateral Factor} = 1 - \text{Collateral Ratio}
     \]

6. **Composite Risk (Heat) Index Calculation:**  
   - The system uses a multiplicative model exclusively. The composite risk index is calculated using the formula:
     \[
     R = \left(\text{Distance Factor}\right)^{0.45} \times \left(\text{Normalized Leverage}\right)^{0.35} \times \left(\text{Risk Collateral Factor}\right)^{0.20} \times 100
     \]
   - Round the final result to two decimal places.
   - This value is reported on a 0–100 scale, where higher values denote higher risk.

7. **Differential Risk:**  
   - For systems managing both long and short positions, compute:
     \[
     \Delta R = R_{\text{long}} - R_{\text{short}}
     \]
   - This differential helps determine which side of the hedge is riskier.

### 3.2 Non-Functional Requirements

- **Dynamic Recalculation:**  
  The risk index must update in real-time as the simulated price changes (integrated in the UI via JavaScript).

- **Parameter Tuning:**  
  The exponents (0.45, 0.35, 0.20) and the normalization factor for leverage (dividing by 100) are based on internal testing and can be adjusted as needed for back-testing and calibration.

- **Error Handling and Logging:**  
  Invalid or missing inputs (e.g., non-positive prices or collateral) should result in the function returning `None` and logging an appropriate error message to facilitate debugging.

- **Reporting:**  
  The system should report both the raw composite risk index and its normalized version (0–100) for each position. These values are used in the UI to display the “heat index” dynamically.

## 4. Design Considerations

### 4.1 Normalization Strategy

- **Distance to Liquidation:**  
  A lower NDL (i.e., a higher distance factor) indicates higher risk. Clamping ensures the value remains within a meaningful range.

- **Leverage:**  
  Dividing by 100 standardizes leverage. This method assumes that while leverage values can vary, a direct scaling is sufficient for risk contribution.

- **Collateral Ratio:**  
  Expressed as a fraction (capped at 1) to ensure positions with excessive collateral do not disproportionately lower the risk index.

### 4.2 Model Choice

- **Multiplicative Model:**  
  - **Pros:**  
    - Captures the compounding effect of adverse factors.
    - Sensitive to extreme values, highlighting positions that are particularly vulnerable.
  - **Cons:**  
    - Can be overly sensitive if one of the inputs is an outlier.
  - **Note:** Although an additive model was considered, the latest implementation uses the multiplicative approach exclusively.

### 4.3 Weight and Exponent Calibration

- **Current Exponents:**  
  - Distance Factor exponent: 0.45  
  - Normalized Leverage exponent: 0.35  
  - Collateral Risk Factor exponent: 0.20  
- These were selected based on internal analysis and can be tuned further based on historical performance data and market conditions.

## 5. Implementation Workflow

1. **Input Validation:**  
   - Confirm all required fields are provided and valid.
   - Ensure that `entry_price`, `liquidation_price`, `collateral`, and `size` are positive and that the gap between `entry_price` and `liquidation_price` is significant.

2. **Calculation of NDL:**  
   - Compute NDL based on the position type (LONG or SHORT) and clamp to [0, 1].

3. **Calculation of Intermediate Factors:**  
   - **Distance Factor:** \(1 - \text{NDL}\)
   - **Normalized Leverage:** \(\text{leverage} / 100\)
   - **Risk Collateral Factor:** \(1 - \min(\text{collateral} / \text{size}, 1)\)

4. **Composite Risk Index Computation:**  
   - Apply the multiplicative formula:
     \[
     R = (\text{Distance Factor})^{0.45} \times (\text{Normalized Leverage})^{0.35} \times (\text{Risk Collateral Factor})^{0.20} \times 100
     \]
   - Round \(R\) to two decimal places.

5. **Integration with UI:**  
   - The computed risk index is used to display the “heat index” for both long and short positions.
   - JavaScript functions in the Hedge Calculator (e.g., `updateLongHeatIndex` and `updateShortHeatIndex`) call the composite risk formula dynamically as the simulated price changes.
   - The risk index is also stored and may be updated in the database via the aggregator logic in the backend.

6. **Error Logging:**  
   - Any exceptions or invalid input scenarios are logged to a dedicated file (e.g., `calc_services.log`) for further analysis.

## 6. Future Extensions

- **Incorporating Additional Factors:**  
  Future iterations may include financing costs, fees, or volatility adjustments to further refine the risk assessment.

- **Enhanced Calibration:**  
  Implement real-time calibration using live market data to continuously update the normalization and exponent parameters.

- **Alternate Models:**  
  Although the current system exclusively uses the multiplicative model, future versions might allow switching between additive and multiplicative models based on user preference or market conditions.

## 7. Appendices

### Appendix A: Example Calculations

#### Example 1: Long Position
- **Entry Price:** \$100  
- **Liquidation Price:** \$80  
- **Current Price:** \$90  
- **NDL Calculation:**  
  \[
  \text{NDL} = \frac{90 - 80}{100 - 80} = \frac{10}{20} = 0.5
  \]
- **Distance Factor:**  
  \(1 - 0.5 = 0.5\)
- **Leverage:** 10x  
  **Normalized Leverage:**  
  \(10 / 100 = 0.10\)
- **Collateral Ratio:** 0.5 (if collateral is half the position size)  
  **Risk Collateral Factor:**  
  \(1 - 0.5 = 0.5\)
- **Composite Risk Index:**  
  \[
  R = (0.5)^{0.45} \times (0.10)^{0.35} \times (0.5)^{0.20} \times 100
  \]
  (Result rounded to two decimals; the exact value depends on the computed intermediate values.)

#### Example 2: Short Position
- Follow a similar process using the adjusted NDL formula for short positions:
  \[
  \text{NDL} = \frac{\text{liquidation price} - \text{current price}}{\text{liquidation price} - \text{entry price}}
  \]

### Appendix B: Data Requirements

- **Trade and Position Data:**  
  Historical and live data including entry price, liquidation price, collateral, size, and leverage.
- **Market Price Feeds:**  
  Simulated or live price feeds to update the risk index dynamically.
- **Logging Data:**  
  Detailed logs for debugging and validation stored in `calc_services.log`.

### Appendix C: Calibration Guidelines

- **Weights/Exponents:**  
  - Start with exponents: 0.45 (distance), 0.35 (leverage), 0.20 (collateral).
  - Adjust based on back-testing results and market behavior.
- **Normalization Factors:**  
  - Leverage is normalized by dividing by 100. This parameter may be adjusted if positions routinely exceed 100x leverage.
- **Back-Testing:**  
  - Use historical liquidation events and margin call data to refine the model.
  - Continuously compare computed risk indices with real outcomes to ensure the model’s predictive validity.
