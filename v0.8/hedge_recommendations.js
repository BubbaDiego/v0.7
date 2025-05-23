/**
 * hedge_recommendations.js
 *
 * This module encapsulates the hedge recommendation logic used in the Hedge Calculator.
 *
 * It supports multiple recommendation profiles. The default profile uses a closed-form
 * solution that calculates the additional position size (delta) needed to adjust the
 * weighted entry price such that the resulting safety margin equals the target.
 *
 * THEORY & CALCULATION:
 * -----------------------------------------------------------------------------
 * For a long position, the safety margin is defined as:
 *    Margin = (Simulated Price - Liquidation Price) / (Entry Price - Liquidation Price)
 *
 * When adding an extra position (delta) at the simulated price, the new weighted entry
 * price becomes:
 *    E_new = (Current_Size * Entry_Price + delta * Simulated_Price) / (Current_Size + delta)
 *
 * We set the desired condition:
 *    (Simulated Price - Liquidation Price) / (E_new - Liquidation Price) = Target_Margin
 *
 * Solving for delta (the additional position size), we get:
 *    delta = Current_Size * [Target_Margin*(Entry_Price - Liquidation_Price) - (Simulated_Price - Liquidation_Price)]
 *            / [ (Simulated_Price - Liquidation_Price) * (1 - Target_Margin) ]
 *
 * A similar derivation applies for short positions, with the roles of entry and liquidation
 * prices reversed.
 *
 * This module exports functions to compute the recommendation delta for both long and short
 * positions, as well as a wrapper function to support multiple recommendation profiles.
 */

 // Compute the extra long position delta needed to hit the target safety margin.
function defaultLongRecommendation(simPrice, longEntry, longSize, longLiq, targetMargin) {
  // Ensure we have valid inputs: simPrice must be greater than longLiq and targetMargin != 1.
  if (simPrice <= longLiq || targetMargin === 1) {
    return 0;
  }
  // Closed-form solution based on the derivation above.
  let delta = longSize * (targetMargin * (longEntry - longLiq) - (simPrice - longLiq))
              / ((simPrice - longLiq) * (1 - targetMargin));
  return delta;
}

// Compute the extra short position delta needed to hit the target safety margin.
function defaultShortRecommendation(simPrice, shortEntry, shortSize, shortLiq, targetMargin) {
  // For short positions, we need simPrice to be below the liquidation price.
  if (shortLiq <= simPrice || targetMargin === 1) {
    return 0;
  }
  // Closed-form solution for the short side:
  let delta = shortSize * (targetMargin * (shortLiq - shortEntry) - (shortLiq - simPrice))
              / ((shortLiq - simPrice) * (1 - targetMargin));
  return delta;
}

/**
 * getHedgeRecommendations - Main function to get hedge recommendations.
 *
 * This function selects the appropriate recommendation profile (default in this case)
 * and returns an object with the long and short adjustment deltas.
 *
 * @param {number} simPrice       - The current simulated price.
 * @param {number} longEntry      - The entry price for the long position.
 * @param {number} longSize       - The current size (in USD) of the long position.
 * @param {number} longLiq        - The liquidation price for the long position.
 * @param {number} shortEntry     - The entry price for the short position.
 * @param {number} shortSize      - The current size (in USD) of the short position.
 * @param {number} shortLiq       - The liquidation price for the short position.
 * @param {number} targetMargin   - The target safety margin (as a fraction, e.g., 0.15 for 15%).
 * @param {string} [profile="default"] - (Optional) The recommendation profile to use.
 *
 * @returns {Object} An object with properties { longDelta, shortDelta }
 */
function getHedgeRecommendations(simPrice, longEntry, longSize, longLiq,
                                 shortEntry, shortSize, shortLiq, targetMargin, profile = "default") {
  let longDelta, shortDelta;
  if (profile === "default") {
    longDelta = defaultLongRecommendation(simPrice, longEntry, longSize, longLiq, targetMargin);
    shortDelta = defaultShortRecommendation(simPrice, shortEntry, shortSize, shortLiq, targetMargin);
  } else {
    // Future: Implement alternative recommendation profiles here.
    longDelta = defaultLongRecommendation(simPrice, longEntry, longSize, longLiq, targetMargin);
    shortDelta = defaultShortRecommendation(simPrice, shortEntry, shortSize, shortLiq, targetMargin);
  }
  return { longDelta, shortDelta };
}

// Export the functions for use in your main Hedge Calculator.
export { getHedgeRecommendations, defaultLongRecommendation, defaultShortRecommendation };
