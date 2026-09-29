import numpy as np
import pandas as pd
from xgboost import XGBClassifier, XGBRegressor


class TreeHouse:
    def __init__(self):
        # Stage 1: Route to Category
        self.category_classifier = XGBClassifier()

        # Stage 2: Route to Price Tier (nested by category)
        self.tier_classifiers = {}

        # Stage 3: Specialized Regressors (nested by category and tier)
        self.regressors = {}

    def fit(self, X, y, categories, price_tiers):
        """
        X: Tabular features DataFrame
        y: Raw prices Series
        categories: Category labels (e.g., 'electronics', 'apparel')
        price_tiers: Tier labels (e.g., 'budget', 'premium')
        """
        # --- STAGE 1: Train Category Classifier ---
        print("Training Stage 1: Category Router...")
        self.category_classifier.fit(X, categories)

        # --- STAGE 2 & 3: Train Tier Classifiers and Leaf Regressors ---
        unique_cats = np.unique(categories)
        for cat in unique_cats:
            cat_mask = categories == cat
            X_cat = X[cat_mask]
            tiers_cat = price_tiers[cat_mask]
            y_cat = y[cat_mask]

            print(f"Training Stage 2: Price Tier Classifier for {cat}...")
            tier_model = XGBClassifier(eval_metric="logloss")
            tier_model.fit(X_cat, tiers_cat)
            self.tier_classifiers[cat] = tier_model

            # Train an expert regressor for every single Category -> Tier combination
            unique_tiers = np.unique(tiers_cat)
            for tier in unique_tiers:
                tier_mask = tiers_cat == tier
                X_leaf = X_cat[tier_mask]

                # Log-transforming price to normalize scale variations
                y_leaf = np.log1p(y_cat[tier_mask])

                print(f"  -> Training Stage 3: Expert Regressor for {cat} [{tier}]...")
                regressor = XGBRegressor(n_estimators=50, max_depth=4)
                regressor.fit(X_leaf, y_leaf)

                # Store the model using a composite key
                self.regressors[f"{cat}_{tier}"] = regressor

    def predict_single(self, x_item):
        """Predicts the price of a single item vector (1D array/DataFrame row)"""
        # Convert to 2D array for sklearn compatibility
        x_reshaped = (
            x_item.values.reshape(1, -1)
            if isinstance(x_item, pd.Series)
            else x_item.reshape(1, -1)
        )

        # 1. Predict Category
        pred_cat = self.category_classifier.predict(x_reshaped)[0]

        # 2. Predict Price Tier using that specific category's classifier
        pred_tier = self.tier_classifiers[pred_cat].predict(x_reshaped)[0]

        # 3. Predict Exact Log-Price using the assigned Expert Regressor
        leaf_key = f"{pred_cat}_{pred_tier}"
        predicted_log_price = self.regressors[leaf_key].predict(x_reshaped)[0]

        # Inverse log-transform back to real dollar amount (e.g., e^x - 1)
        return np.expm1(predicted_log_price), pred_cat, pred_tier
