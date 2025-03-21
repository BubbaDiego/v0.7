# Hedge Calculator Risk Index Mini Case Study

This case study examines three test cases where a single weight factor is maximized to extreme values. Each test isolates one of the three core components of the heat index—Distance to Liquidation, Leverage, and Collateral—to observe its impact on the risk scores for long and short positions. In each test, we focus only on the **top heat index** box for each position, ignoring the purple sim index.

---

## 1. Data Analysis

### Test A – Distance Factor at Extreme Weight (90%)
- **Observation:**  
  - The **long position’s heat index** is approximately **23.8**.
  - The **short position’s heat index** is around **73.3**.
- **Explanation:**  
  - Here, the **Distance to Liquidation** factor dominates the calculation. The short position is near its liquidation point (NDL near 0), resulting in a high risk score, while the long position (far from liquidation) remains relatively low.
  - The multiplicative model, which raises the normalized factors to specific exponents, means that a 90% emphasis on distance dramatically skews the composite index toward the risk inherent in proximity to liquidation.
- **Conclusion:**  
  - This confirms that when the distance factor is heavily weighted, the risk index effectively captures the imminent danger of nearing liquidation.

### Test B – Leverage Factor at Extreme Weight (90%)
- **Observation:**  
  - The **long position’s heat index** is about **21.0**.
  - The **short position’s heat index** is approximately **52.4**.
- **Explanation:**  
  - In this scenario, leverage is the primary driver. The short position’s higher leverage (50× vs. ~19× for the long) leads to a significantly higher risk score.
  - Despite not being close to liquidation, the high leverage amplifies potential losses. The normalized leverage (leverage/100) raised to the specified exponent highlights the dangers of high leverage.
- **Conclusion:**  
  - The test clearly shows that high leverage, when emphasized, increases the risk score considerably even if other factors (distance and collateral) are relatively safe.

### Test C – Collateral Factor at Extreme Weight (90%)
- **Observation:**  
  - The heat index ranking flips compared to the previous tests: the **long position** (with a very low collateral ratio, around 5%) is evaluated as higher-risk than the short (with a collateral ratio of ~25%).
- **Explanation:**  
  - When collateral is prioritized, the risk model focuses on the adequacy of the collateral backing the position. A poor collateral-to-position ratio (risk collateral factor computed as `1 – collateral_ratio`) results in a high risk score.
  - Even if a position is not near liquidation or heavily leveraged, insufficient collateral can make it highly vulnerable.
- **Conclusion:**  
  - This test demonstrates that the model correctly penalizes positions with weak collateralization, thereby highlighting potential vulnerabilities that might not be apparent from distance or leverage alone.

---

## 2. Findings and Observations

- **Distance to Liquidation:**  
  - When heavily weighted, it produces the most dramatic risk differences. Positions near liquidation show a sharply increased heat index.
- **Leverage:**  
  - High leverage significantly boosts the risk index, even if the position isn’t imminently at risk of liquidation. However, the effect is more moderate compared to an extreme distance factor.
- **Collateral:**  
  - Poor collateralization can override other seemingly favorable conditions. The model flags positions with insufficient collateral, even if other risk parameters are moderate.
- **Overall Insight:**  
  - Each factor behaves as expected when isolated. The tests validate that extreme weighting magnifies the influence of each factor and, importantly, can alter the relative risk ranking between long and short positions.

---

## 3. Comparison to Existing Risk Models

- **Traditional Margin Ratios:**  
  - Most exchanges use margin ratios (e.g., reaching 100% margin triggers liquidation). This single-factor approach often only indicates risk when a position is nearly liquidated.
  - In contrast, our composite index flags high-risk positions earlier by integrating leverage and collateral considerations.
  
- **Leverage as a Standalone Metric:**  
  - Pure leverage limits are common, but they lack the nuance of context. Our model contextualizes leverage with both the distance to liquidation and the collateral ratio, providing a richer risk profile.
  
- **Volatility and VaR Approaches:**  
  - Traditional risk measures like Value-at-Risk (VaR) incorporate market volatility, but are more complex to compute on a per-position basis.
  - The heat index, while not directly including volatility, offers a continuous gradation of risk from 0 to 100, which can be more intuitive for traders assessing immediate position health.
  
- **Risk Prioritization:**  
  - Unlike binary thresholds, the continuous scale of the heat index allows for better risk comparison between positions. For instance, even if two positions are under a safe margin threshold, a higher heat index on one indicates it may deteriorate faster under stress.

---

## 4. Bringing It All Together

### Key Takeaways
- **Multi-Dimensional Risk Assessment:**  
  - The heat index effectively combines distance to liquidation, leverage, and collateral to provide a holistic risk measure.
- **Sensitivity to Extreme Conditions:**  
  - Extreme weighting tests show that each factor dramatically alters the heat index in line with intuitive risk—especially in highlighting positions near liquidation or with poor collateral.
- **Complementary to Existing Metrics:**  
  - Compared to traditional risk indicators, the heat index offers early warnings and more nuanced insights into risk. It complements conventional margin ratios and leverage limits by revealing hidden vulnerabilities.
  
### Potential Next Steps
- **Calibration Refinement:**  
  - Fine-tune the weights/exponents to ensure that no single factor can dominate under normal conditions. Re-calibrate using real trading data and historical liquidation events.
- **Smoothing Mechanisms:**  
  - Explore adding a smoothing or additive component to prevent the index from being too extreme when one factor is at an outlier value.
- **Incorporate Additional Factors:**  
  - Consider integrating market volatility or dynamic adjustments based on external factors to enhance predictive power.
- **Benchmarking and Validation:**  
  - Conduct further back-testing against live data to verify that the heat index correlates with actual risk outcomes. Compare performance with standard industry benchmarks and adjust as needed.
- **User Education:**  
  - Develop UI tooltips or documentation that explain the heat index, helping traders understand how each factor contributes to overall risk.

---

# Updated Key Takeaway: Accounting for Residual Market Risk

Based on our initial testing of the 3-factor index under extreme conditions, an important observation emerged:

- **Fully Collateralized Positions and Residual Market Risk:**  
  In the current model, a fully collateralized position (i.e., a collateral ratio of 100%) yields a heat index of **0**. This result effectively signals "no risk" from the perspective of liquidation risk. However, it is important to note that even a fully collateralized position is not risk-free—it remains exposed to market risk, meaning the position can still lose value despite not being forced closed.

### Considerations for Improvement

- **Incorporating a Risk Floor or Additive Term:**  
  To better capture the reality that risk always exists, one potential improvement is to introduce a risk floor or additive constant into the model. This would ensure that the heat index never drops to zero, reflecting that even in the best-case scenario, there is always some inherent market risk.

- **Potential Approaches:**
  - **Additive Offset:**  
    Add a small constant (e.g., 5 or 10 points) to the final composite score so that even a fully collateralized position starts with a baseline risk level.
  - **Minimum Risk Floor:**  [calc_services.py](utils/calc_services.py)
    Set a lower bound for the heat index (e.g., 5 on a scale of 0–100) to acknowledge residual market risk.
  - **Volatility Adjustment:**  
    Incorporate a volatility or market risk factor into the formula. Even if the position is fully collateralized, higher market volatility would increase the risk index slightly.

# Updated Key Takeaway: Incorporating a Minimum Risk Floor

Based on our initial testing of the 3-factor index under extreme conditions, we observed that a fully collateralized position (i.e., a collateral ratio of 100%) yields a heat index of **0**. While this outcome effectively indicates “no risk” from the standpoint of liquidation, it fails to account for the residual market risk inherent in every position. Even if a position is fully collateralized and cannot be force-closed, it can still lose value due to market fluctuations.

### Proposed Improvement: Minimum Risk Floor

To address this shortcoming, we propose incorporating a **minimum risk floor of 5** into the composite risk index. This means that regardless of how favorable the position metrics are (even with a 100% collateral ratio), the heat index will never fall below 5. This adjustment ensures that the model reflects the reality that some risk always exists, even in the best-case scenario.

#### Implementation Details
- **Additive Offset:**  
  After computing the composite risk index using the multiplicative model, the final value will be adjusted such that if the result is less than 5, it will be set to 5.
- **Rationale:**  
  By setting a baseline risk value of 5, we ensure that every position is recognized as having at least a minimal level of risk, thereby better capturing the inherent market risk that exists independently of liquidation risk.

### Benefits of This Approach
- **Realistic Risk Assessment:**  
  A minimum risk floor acknowledges that risk is never truly zero, even in fully collateralized scenarios.
- **Enhanced Decision-Makin[calc_services.py](utils/calc_services.py)g:**  
  Traders receive a more nuanced risk signal, helping them understand that a “perfect” collateral scenario does not equate to complete safety.
- **Model Robustness:**  
  The adjustment prevents misleading interpretations that could arise from a zero-risk reading, thereby fostering more prudent risk management.

---

*End of Updated Takeaway Section*


### Open Discussion

This update is a crucial consideration for refining the index. While the current multiplicative model accurately reflects liquidation risk, it may undervalue the continuous presence of market risk in fully collateralized positions.  
**I’m open to suggestions on how we can best implement this improvement.** Your ideas on the appropriate additive value or alternative methods to account for baseline risk are welcome.

---

*End of Updated Takeaway Section*

  
## Conclusion

The 3-factor heat index proves to be a valuable tool for assessing risk in hedged positions. Its ability to integrate distance to liquidation, leverage, and collateral provides a comprehensive and nuanced view of risk. While traditional risk models focus on single factors (like margin ratio), this composite index offers early, actionable insights into potential vulnerabilities. The study confirms that each component of the index behaves logically when isolated and that the overall model can effectively prioritize risk. With further refinement and calibration, this heat index can serve as a robust risk assessment tool in live trading environments, helping traders manage their positions more proactively.

Update:  Based on the results on this initial 3 factor index testing at extremes. the following is the key take away to is be consider.   In practice, a fully collateralized position (collateral ratio 100%) yields a heat index of 0 in this model – essentially saying “no risk.” While that makes sense in terms of avoiding liquidation, such a position still has market risk (it can lose value, though it won’t be force-closed). We might consider if the index should always have some floor or additive term so that risk isn’t ever literally zero.

*End of Report*
