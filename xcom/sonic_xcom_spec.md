Hedge Calculator – Three Position-Adjustment Approaches
This specification details the three primary approaches the Hedge Calculator can use to recommend position adjustments: Average Down, Pyramid, and Equilibrium. Each approach serves a different trading style or goal, and each uses the same fundamental building blocks—liquidation margins, target safety margins, and position sizing logic—but applies them in different ways.

Below is an overview of the rationale, calculation steps, strengths, and weaknesses for each approach.

1. Core Concepts and Inputs
Before diving into each approach, here are the core concepts shared by all three:

Safety Margin Calculation

For a long position, safety margin is computed as:

Margin
long
=
Simulated Price
−
Liquidation Price
Entry Price
−
Liquidation Price
Margin 
long
​
 = 
Entry Price−Liquidation Price
Simulated Price−Liquidation Price
​
 
Clamped between 0 and 1.

For a short position, safety margin is computed as:

Margin
short
=
Liquidation Price
−
Simulated Price
Liquidation Price
−
Entry Price
Margin 
short
​
 = 
Liquidation Price−Entry Price
Liquidation Price−Simulated Price
​
 
Also clamped between 0 and 1.

Target Safety Margin

A user-defined percentage (e.g., 15%) that indicates the desired buffer above liquidation.

If the actual margin is below this target, the system typically recommends increasing position size (or collateral) on that side to push liquidation farther away.

If the actual margin is above this target, the system may recommend re-balancing or pyramiding to capitalize on momentum.

Adjustment Factor

A scalar that controls how aggressively the system attempts to correct a margin shortfall or exceedance.

Typically, recommended size adjustments are multiplied by this factor.

A higher adjustment factor means larger recommended additions; a lower factor yields more conservative changes.

Position Sizing

In each approach, the system typically calculates a difference between the current margin and the target margin.

This difference is then multiplied by the existing position size (and possibly scaled further by the adjustmentFactor) to produce a recommended add-on or offset.

2. Approach A: Average Down
2.1 Overview
Average Down is the classic approach for adjusting positions when the market moves against you. The logic:

If the actual margin is below the target, it implies your position is “in danger” (liquidation is relatively close). The system recommends adding more size (or collateral) on that side to push the liquidation point away.

If the actual margin is above the target, it does nothing—the position is “safe enough.”

Hence the name “average down,” because you typically add to a losing position in order to lower your average entry price (long) or raise it (short).

2.2 Calculation Steps
Compute safety margin (long or short).

Compare margin to the target margin.

If 
margin
<
target
margin<target, recommended add =

(
target
−
margin
)
×
currentSize
×
adjustmentFactor
.
(target−margin)×currentSize×adjustmentFactor.
If 
margin
≥
target
margin≥target, recommended add = 0.

2.3 Strengths
Simple: Easiest approach to understand—only intervene when in danger.

Prevents Forced Liquidation: Helps keep you from crossing the liquidation threshold if you believe the market will eventually reverse.

2.4 Weaknesses
Risk of Overexposure: Continuously adding to a losing position can lead to large drawdowns if the market keeps moving against you.

Missed Opportunities: Doesn’t pyramid or add to winning positions, so you might miss compounding gains when you’re right.

3. Approach B: Pyramid
3.1 Overview
Pyramid is essentially the opposite of average down. You add to a winning position when your margin is already above the target, believing that a trend will continue in your favor. You do not intervene when the margin is below the target (i.e., you don’t “save” a losing side).

3.2 Calculation Steps
Compute safety margin.

Compare margin to the target margin.

If 
margin
>
target
margin>target, recommended add =

(
margin
−
target
)
×
currentSize
×
adjustmentFactor
.
(margin−target)×currentSize×adjustmentFactor.
If 
margin
≤
target
margin≤target, recommended add = 0.

3.3 Strengths
Momentum-Friendly: Builds a bigger position in the direction of profit. Potentially amplifies gains if the trend persists.

Stops Over-Leveraging in Losing Trades: Doesn’t average down or “throw good money after bad.”

3.4 Weaknesses
No Liquidation Protection: Does little or nothing when your margin is below the target. If the market moves against you, you won’t add collateral to protect from liquidation.

Potential Overconfidence: If a strong trend abruptly reverses, you could be left with a larger position in the losing direction.

4. Approach C: Equilibrium
4.1 Overview
Equilibrium aims to keep both sides balanced around the same (or similar) safety margin. It effectively tries to maintain a mid-range margin on both your long and short. If one side’s margin is too high (i.e., that side is in profit), it might add to the other side to keep them matched. Conversely, if one side’s margin is too low, it will add to that side.

This approach can be seen as a two-sided balancing act, constantly nudging each side toward a desired equilibrium margin.

4.2 Calculation Steps
Compute safety margin for both sides.

For each side (long or short):

If 
margin
side
<
target
margin 
side
​
 <target, recommend an addition to that side.

If 
margin
side
>
target
margin 
side
​
 >target, you might also recommend adding to the other side (to keep them in sync).

The recommended size additions often use a formula like:

(
target
−
margin
side
)
×
currentSize
side
×
adjustmentFactor
.
(target−margin 
side
​
 )×currentSize 
side
​
 ×adjustmentFactor.
or a symmetrical approach for margin above target.

Note: The exact logic can vary: some equilibrium modes only add to the weaker side; others reduce from the stronger side or do a combination of both.

4.3 Strengths
Balanced Risk: Helps ensure that neither side is drastically closer to liquidation.

Smooth Adjustments: Tends to avoid extremes (not heavily pyramiding nor heavily averaging down).

4.4 Weaknesses
Potential Over-Trading: Because it constantly seeks balance, it might keep making small “tweaks” on each side, which can rack up fees.

Difficult to Exploit Trends: By always re-balancing, you might not benefit as much from letting one winning side run.

5. Comparison Table
Approach	When It Adds	Focus	Strengths	Weaknesses
Average Down	If margin < target	Protect from liquidation	- Simple to understand
- Good for preventing forced closure	- Can overexpose if market keeps moving against you
- Doesn’t add to winning positions
Pyramid	If margin > target	Ride profitable trends	- Amplifies gains in strong trends
- Avoids throwing money at losers	- Provides no margin rescue if position is losing
- Potentially large position if trend reverses
Equilibrium	If margin ≠ target	Keep both sides balanced	- Maintains moderate risk on both sides
- Avoids extremes of average down/pyramid	- May lead to frequent re-balancing (fee-heavy)
- Harder to capture large trending moves
6. Implementation Notes
Adjustment Factor

In each approach, the recommended addition is scaled by adjustmentFactor. This prevents the system from going “all in” at once and fosters incremental adjustments.

Partial Convergence

After one recommendation, the margin might move closer to the target but not fully reach it—hence repeated suggestions if you re-run the calculator.

Liquidation Price Updates

Whenever you add to a position (or add collateral), the liquidation price can change. This is accounted for in the next iteration of the safety margin calculation.

Fee Considerations

Each recommended addition typically includes an estimate of fees (a percentage of total notional). That cost is subtracted from the net P&L or position value.

7. Conclusion
Each approach—Average Down, Pyramid, and Equilibrium—caters to a different style of risk management and strategy:

Average Down focuses on saving losing trades from liquidation.

Pyramid doubles down on winning trades, ignoring losing trades.

Equilibrium tries to keep a balanced posture on both sides, adjusting whichever side deviates from the target margin.

The Hedge Calculator’s underlying math is consistent: it measures how close or far each position is from liquidation, compares that to a user-defined target margin, and uses a scaled “adjustment factor” to propose how much to add. By choosing the approach that aligns with your personal trading philosophy—capital preservation vs. momentum exploitation vs. balanced hedging—you can tailor the Hedge Calculator to suit your risk preferences.