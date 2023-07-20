import pandas as pd
import numpy as np
import math
from .Types import *
from . import MLExtensions as ml
from . import KernelFunctions as kernels
import talib as ta

# ====================
# ==== Background ====
# ====================

# When using Machine Learning algorithms like K-Nearest Neighbors, choosing an
# appropriate distance metric is essential. Euclidean Distance is often used as
# the default distance metric, but it may not always be the best choice. This is
# because market data is often significantly impacted by proximity to significant
# world events such as FOMC Meetings and Black Swan events. These major economic
# events can contribute to a warping effect analogous a massive object's 
# gravitational warping of Space-Time. In financial markets, this warping effect 
# operates on a continuum, which can analogously be referred to as "Price-Time".

# To help to better account for this warping effect, Lorentzian Distance can be
# used as an alternative distance metric to Euclidean Distance. The geometry of
# Lorentzian Space can be difficult to visualize at first, and one of the best
# ways to intuitively understand it is through an example involving 2 feature
# dimensions (z=2). For purposes of this example, let's assume these two features
# are Relative Strength Index (RSI) and the Average Directional Index (ADX). In
# reality, the optimal number of features is in the range of 3-8, but for the sake
# of simplicity, we will use only 2 features in this example.

# Fundamental Assumptions:
# (1) We can calculate RSI and ADX for a given chart.
# (2) For simplicity, values for RSI and ADX are assumed to adhere to a Gaussian 
#     distribution in the range of 0 to 100.
# (3) The most recent RSI and ADX value can be considered the origin of a coordinate 
#     system with ADX on the x-axis and RSI on the y-axis.

# Distances in Euclidean Space:
# Measuring the Euclidean Distances of historical values with the most recent point
# at the origin will yield a distribution that resembles Figure 1 (below).

#                        [RSI]
#                          |                      
#                          |                   
#                          |                 
#                      ...:::....              
#                .:.:::••••••:::•::..             
#              .:•:.:•••::::••::••....::.            
#             ....:••••:••••••••::••:...:•.          
#            ...:.::::::•••:::•••:•••::.:•..          
#            ::•:.:•:•••••••:.:•::::::...:..         
#  |--------.:•••..•••••••:••:...:::•:•:..:..----------[ADX]    
#  0        :•:....:•••••::.:::•••::••:.....            
#           ::....:.:••••••••:•••::••::..:.          
#            .:...:••:::••••••••::•••....:          
#              ::....:.....:•::•••:::::..             
#                ..:..::••..::::..:•:..              
#                    .::..:::.....:                
#                          |            
#                          |                   
#                          |
#                          |
#                         _|_ 0        
#                          
#        Figure 1: Neighborhood in Euclidean Space

# Distances in Lorentzian Space:
# However, the same set of historical values measured using Lorentzian Distance will 
# yield a different distribution that resembles Figure 2 (below).

#                         
#                         [RSI] 
#  ::..                     |                    ..:::  
#   .....                   |                  ......
#    .••••::.               |               :••••••. 
#     .:•••••:.             |            :::••••••.  
#       .•••••:...          |         .::.••••••.    
#         .::•••••::..      |       :..••••••..      
#            .:•••••••::.........::••••••:..         
#              ..::::••••.•••••••.•••••••:.            
#                ...:•••••••.•••••••••::.              
#                  .:..••.••••••.••••..                
#  |---------------.:•••••••••••••••••.---------------[ADX]          
#  0             .:•:•••.••••••.•••••••.                
#              .••••••••••••••••••••••••:.            
#            .:••••••••••::..::.::••••••••:.          
#          .::••••••::.     |       .::•••:::.       
#         .:••••••..        |          :••••••••.     
#       .:••••:...          |           ..•••••••:.   
#     ..:••::..             |              :.•••••••.   
#    .:•....                |               ...::.:••.  
#   ...:..                  |                   :...:••.     
#  :::.                     |                       ..::  
#                          _|_ 0
#
#       Figure 2: Neighborhood in Lorentzian Space 


# Observations:
# (1) In Lorentzian Space, the shortest distance between two points is not 
#     necessarily a straight line, but rather, a geodesic curve.
# (2) The warping effect of Lorentzian distance reduces the overall influence  
#     of outliers and noise.
# (3) Lorentzian Distance becomes increasingly different from Euclidean Distance 
#     as the number of nearest neighbors used for comparison increases.

class LorentzianClassification:
    
    from .Types import Feature, Settings, FilterSettings

    df: pd.DataFrame = None
    features = list[pd.Series]()
    settings: Settings
    filterSettings: FilterSettings
    # Filter object for filtering the ML predictions
    filter: Filter

    yhat1: pd.Series
    yhat2: pd.Series


    # Feature Variables: User-Defined Inputs for calculating Feature Series.
    # Options: ["RSI", "WT", "CCI", "ADX"]
    # FeatureSeries Object: Calculated Feature Series based on Feature Variables
    def series_from(data: pd.DataFrame, feature_string, f_paramA, f_paramB) -> pd.Series:
        match feature_string:
            case "RSI":
                return ml.n_rsi(data['close'], f_paramA, f_paramB)
            case "WT":
                hlc3 = (data['high'] + data['low'] + data['close']) / 3
                return ml.n_wt(hlc3, f_paramA, f_paramB)
            case "CCI":
                return ml.n_cci(data['high'], data['low'], data['close'], f_paramA, f_paramB)
            case "ADX":
                return ml.n_adx(data['high'], data['low'], data['close'], f_paramA)


    def __init__(self, data: pd.DataFrame, features: list = [], settings: Settings = None, filterSettings: FilterSettings = None):
        self.df = data.copy()
        if len(features) == 0:
            features = [
                Feature("RSI", 14, 2),  # f1
                Feature("WT", 10, 11),  # f2
                Feature("CCI", 20, 2),  # f3
                Feature("ADX", 20, 2),  # f4
                Feature("RSI", 9, 2),   # f5
            ]
        if settings == None:
            settings = Settings(
                source='close',
                neighborsCount = 8,
                maxBarsBack = 2000,
                featureCount = 5,
                colorCompression = 1,
                showDefaultExits = False,
                useDynamicExits = False
            )
        if filterSettings == None:
            filterSettings = FilterSettings(
                useVolatilityFilter = True,
                useRegimeFilter = True,
                useAdxFilter = False,
                regimeThreshold=-0.1,
                adxThreshold = 20
            )
        for f in features:
            if type(f) == Feature:
                self.features.append(LorentzianClassification.series_from(data, f.type, f.param1, f.param2))
            else:
                self.features.append(f)
        self.settings = settings
        self.filterSettings = filterSettings
        self.filter = Filter(
            volatility = ml.filter_volatility(data['high'], data['low'], data['close'], filterSettings.useVolatilityFilter, 1, 10),
            regime = ml.regime_filter((data['open'] + data['high'] + data['low'] + data['close']) / 4, data['high'], data['low'], filterSettings.useRegimeFilter, filterSettings.regimeThreshold),
            adx = ml.filter_adx(data[settings.source], data['high'], data['low'], filterSettings.adxThreshold, filterSettings.useAdxFilter, 14)
        )
        self.__classify()


    def __get_lorentzian_distance(self, i, bar_index, features: list[pd.Series]):
        retVal = 0
        for feature in features:
            retVal += math.log(1 + abs(feature[bar_index] - feature[i]))
        return retVal


    def __classify(self):
        # Derived from General Settings
        maxBarsBackIndex = (len(self.df.index) - self.settings.maxBarsBack) if (len(self.df.index) >= self.settings.maxBarsBack) else 0
        # EMA Settings
        useEmaFilter = False
        emaPeriod = 200
        self.df["isEmaUptrend"] = (self.df["close"] > ta.EMA(self.df["close"], emaPeriod)) if useEmaFilter else True
        self.df["isEmaDowntrend"] = (self.df["close"] < ta.EMA(self.df["close"], emaPeriod)) if useEmaFilter else True

        # SMA Settings
        useSmaFilter = False
        smaPeriod = 200
        self.df["isSmaUptrend"] = (self.df["close"] > ta.SMA(self.df["close"], smaPeriod)) if useSmaFilter else True
        self.df["isSmaDowntrend"] = (self.df["close"] < ta.SMA(self.df["close"], smaPeriod)) if useSmaFilter else True


        # Nadaraya-Watson Kernel Regression Settings
        useKernelFilter = True  # Trade with Kernel
        showKernelEstimate = True  # Show Kernel Estimate
        useKernelSmoothing = False  # Enhance Kernel Smoothing: Uses a crossover based mechanism to smoothen kernel color changes. This often results in less color transitions overall and may result in more ML entry signals being generated.
        h = 8  # Lookback Window: The number of bars used for the estimation. This is a sliding value that represents the most recent historical bars. Recommended range: 3-50
        r = 8.0  # Relative Weighting: Relative weighting of time frames. As this value approaches zero, the longer time frames will exert more influence on the estimation. As this value approaches infinity, the behavior of the Rational Quadratic Kernel will become identical to the Gaussian kernel. Recommended range: 0.25-25
        x = 25  # Regression Level: Bar index on which to start regression. Controls how tightly fit the kernel estimate is to the data. Smaller values are a tighter fit. Larger values are a looser fit. Recommended range: 2-25
        lag = 2  # Lag: Lag for crossover detection. Lower values result in earlier crossovers. Recommended range: 1-2


        # Display Settings
        showBarColors = True  # Whether to show the bar colors.
        showBarPredictions = True  # Will show the ML model's evaluation of each bar as an integer.
        useAtrOffset = False  # Will use the ATR offset instead of the bar prediction offset.
        barPredictionsOffset = 0.0  # The offset of the bar predictions as a percentage from the bar high or close.


        # =================================
        # ==== Next Bar Classification ====
        # =================================

        # This model specializes specifically in predicting the direction of price action over the course of the next 4 bars. 
        # To avoid complications with the ML model, this value is hardcoded to 4 bars but support for other training lengths may be added in the future.
        src = self.df[self.settings.source]
        y_train_array = np.where(src.shift(4) < src.shift(0), Direction.SHORT, np.where(src.shift(4) > src.shift(0), Direction.LONG, Direction.NEUTRAL))

        # Variables used for ML Logic
        predictions = []
        self.df["prediction"] = 0
        self.df["signal"] = Direction.NEUTRAL
        distances = []


        # =========================
        # ====  Core ML Logic  ====
        # =========================

        # Approximate Nearest Neighbors Search with Lorentzian Distance:
        # A novel variation of the Nearest Neighbors (NN) search algorithm that ensures a chronologically uniform distribution of neighbors.

        # In a traditional KNN-based approach, we would iterate through the entire dataset and calculate the distance between the current bar 
        # and every other bar in the dataset and then sort the distances in ascending order. We would then take the first k bars and use their 
        # labels to determine the label of the current bar. 

        # There are several problems with this traditional KNN approach in the context of real-time calculations involving time series data:
        # - It is computationally expensive to iterate through the entire dataset and calculate the distance between every historical bar and
        #   the current bar.
        # - Market time series data is often non-stationary, meaning that the statistical properties of the data change slightly over time.
        # - It is possible that the nearest neighbors are not the most informative ones, and the KNN algorithm may return poor results if the
        #   nearest neighbors are not representative of the majority of the data.

        # Previously, the user @capissimo attempted to address some of these issues in several of his PineScript-based KNN implementations by:
        # - Using a modified KNN algorithm based on consecutive furthest neighbors to find a set of approximate "nearest" neighbors.
        # - Using a sliding window approach to only calculate the distance between the current bar and the most recent n bars in the dataset.

        # Of these two approaches, the latter is inherently limited by the fact that it only considers the most recent bars in the overall dataset. 

        # The former approach has more potential to leverage historical price action, but is limited by:
        # - The possibility of a sudden "max" value throwing off the estimation
        # - The possibility of selecting a set of approximate neighbors that are not representative of the majority of the data by oversampling 
        #   values that are not chronologically distinct enough from one another
        # - The possibility of selecting too many "far" neighbors, which may result in a poor estimation of price action

        # To address these issues, a novel Approximate Nearest Neighbors (ANN) algorithm is used in this indicator.

        # In the below ANN algorithm:
        # 1. The algorithm iterates through the dataset in chronological order, using the modulo operator to only perform calculations every 4 bars.
        #    This serves the dual purpose of reducing the computational overhead of the algorithm and ensuring a minimum chronological spacing 
        #    between the neighbors of at least 4 bars.
        # 2. A list of the k-similar neighbors is simultaneously maintained in both a predictions array and corresponding distances array.
        # 3. When the size of the predictions array exceeds the desired number of nearest neighbors specified in settings.neighborsCount, 
        #    the algorithm removes the first neighbor from the predictions array and the corresponding distance array.
        # 4. The lastDistance variable is overriden to be a distance in the lower 25% of the array. This step helps to boost overall accuracy 
        #    by ensuring subsequent newly added distance values increase at a slower rate.
        # 5. Lorentzian distance is used as a distance metric in order to minimize the effect of outliers and take into account the warping of 
        #    "price-time" due to proximity to significant economic events.

        for bar_index in range(maxBarsBackIndex, len(src)):
            lastDistance = -1.0
            sizeLoop = min(self.settings.maxBarsBack - 1, bar_index)

            if bar_index >= maxBarsBackIndex:
                for i in range(sizeLoop + 1):
                    d = self.__get_lorentzian_distance(i, bar_index, self.features)
                    if d >= lastDistance and i % 4:
                        lastDistance = d
                        distances.append(d)
                        predictions.append(round(y_train_array[i]))
                        if len(predictions) > self.settings.neighborsCount:
                            lastDistance = distances[round(self.settings.neighborsCount*3/4)]
                            distances.pop(0)
                            predictions.pop(0)
                self.df.loc[self.df.index[bar_index], 'prediction'] = sum(predictions)


        # ============================
        # ==== Prediction Filters ====
        # ============================

        # User Defined Filters: Used for adjusting the frequency of the ML Model's predictions
        filter_all = pd.Series(self.filter.volatility & self.filter.regime & self.filter.adx)

        # Filtered Signal: The model's prediction of future price movement direction with user-defined filters applied
        for i in range(len(self.df.index)):
            prediction = self.df["prediction"].iloc[i]
            self.df.loc[self.df.index[i], "signal"] = Direction.LONG if (prediction > 0 and filter_all[i]) else Direction.SHORT if prediction < 0 and filter_all[i] else self.df["signal"].iloc[i - 1 if i >= 1 else 0]

        change = lambda col, i: self.df[col].iloc[i] != self.df[col].shift(1, fill_value=self.df[col].iloc[0]).iloc[i]

        # Bar-Count Filters: Represents strict filters based on a pre-defined holding period of 4 bars
        self.df["barsHeld"] = 0
        for i in range(len(self.df.index)):
            isDifferentSignalType = change("signal", i)
            self.df.loc[self.df.index[i], "barsHeld"] = 0 if isDifferentSignalType else self.df["barsHeld"].shift(1, fill_value=self.df["barsHeld"].iloc[0]).iloc[i] + 1
            isHeldFourBars = self.df["barsHeld"].iloc[i] == 4
            isHeldLessThanFourBars = 0 <= self.df["barsHeld"].iloc[i] < 4

        # Fractal Filters: Derived from relative appearances of signals in a given time series fractal/segment with a default length of 4 bars
            self.df.loc[self.df.index[i], "isEarlySignalFlip"] = change("signal", i) and (change("signal", i-1) or change("signal", i-2) or change("signal", i-3))
            isBuySignal = self.df["signal"].iloc[i] == Direction.LONG and self.df["isEmaUptrend"].iloc[i] and self.df["isSmaUptrend"].iloc[i]
            isSellSignal = self.df["signal"].iloc[i] == Direction.SHORT and self.df["isEmaDowntrend"].iloc[i] and self.df["isSmaDowntrend"].iloc[i]
            self.df.loc[self.df.index[i], "isLastSignalBuy"] = self.df["signal"].shift(4).iloc[i] == Direction.LONG and self.df["isEmaUptrend"].shift(4).iloc[i] and self.df["isSmaUptrend"].shift(4).iloc[i]
            self.df.loc[self.df.index[i], "isLastSignalSell"] = self.df["signal"].shift(4).iloc[i] == Direction.SHORT and self.df["isEmaDowntrend"].shift(4).iloc[i] and self.df["isSmaDowntrend"].shift(4).iloc[i]
            self.df.loc[self.df.index[i], "isNewBuySignal"] = isBuySignal and isDifferentSignalType
            self.df.loc[self.df.index[i], "isNewSellSignal"] = isSellSignal and isDifferentSignalType


        crossover   = lambda s1, s2: (s1 > s2) & (s1.shift(1) < s2.shift(1))
        crossunder  = lambda s1, s2: (s1 < s2) & (s1.shift(1) > s2.shift(1))

        # Kernel Regression Filters: Filters based on Nadaraya-Watson Kernel Regression using the Rational Quadratic Kernel
        # For more information on this technique refer to my other open source indicator located here:
        # https://www.tradingview.com/script/AWNvbPRM-Nadaraya-Watson-Rational-Quadratic-Kernel-Non-Repainting/
        self.yhat1 = kernels.rationalQuadratic(src, h, r, x)
        self.yhat2 = kernels.gaussian(src, h-lag, x)
        # Kernel Rates of Change
        wasBearishRate = np.where(self.yhat1.shift(2) > self.yhat1.shift(1), True, False)
        wasBullishRate = np.where(self.yhat1.shift(2) < self.yhat1.shift(1), True, False)
        isBearishRate = np.where(self.yhat1.shift(1) > self.yhat1, True, False)
        isBullishRate = np.where(self.yhat1.shift(1) < self.yhat1, True, False)
        isBearishChange = isBearishRate & wasBullishRate
        isBullishChange = isBullishRate & wasBearishRate
        # Kernel Crossovers
        isBullishCrossAlert = crossover(self.yhat2, self.yhat1)
        isBearishCrossAlert = crossunder(self.yhat2, self.yhat1)
        isBullishSmooth = (self.yhat2 >= self.yhat1)
        isBearishSmooth = (self.yhat2 <= self.yhat1)
        # Kernel Colors
        # plot(kernelEstimate, color=plotColor, linewidth=2, title="Kernel Regression Estimate")
        # Alert Variables
        alertBullish = np.where(useKernelSmoothing, isBullishCrossAlert, isBullishChange)
        alertBearish = np.where(useKernelSmoothing, isBearishCrossAlert, isBearishChange)
        # Bullish and Bearish Filters based on Kernel
        isBullish = np.where(useKernelFilter, np.where(useKernelSmoothing, isBullishSmooth, isBullishRate), True)
        isBearish = np.where(useKernelFilter, np.where(useKernelSmoothing, isBearishSmooth, isBearishRate) , True)

        # ===========================
        # ==== Entries and Exits ====
        # ===========================

        def barssince(s: pd.Series):
            if not isinstance(s, pd.Series): s = pd.Series(s)
            val = pd.Series(0, index=s.index)
            c = math.nan
            for i in range(len(s)):
                if s[i]: c = 0; continue
                if c >= 0: c += 1
                val[i] = c
            return val.values

        # Entry Conditions: Booleans for ML Model Position Entries
        startLongTrade = self.df["isNewBuySignal"] & isBullish & self.df["isEmaUptrend"] & self.df["isSmaUptrend"]
        startShortTrade = self.df["isNewSellSignal"] & isBearish & self.df["isEmaDowntrend"] & self.df["isSmaDowntrend"]

        self.df["startLongTrade"] = np.where(startLongTrade, self.df['low'], np.NaN)
        self.df["startShortTrade"] = np.where(startShortTrade, self.df['high'], np.NaN)

        # Dynamic Exit Conditions: Booleans for ML Model Position Exits based on Fractal Filters and Kernel Regression Filters
        lastSignalWasBullish = barssince(startLongTrade) < barssince(startShortTrade)
        lastSignalWasBearish = barssince(startShortTrade) < barssince(startLongTrade)
        barsSinceRedEntry = barssince(startShortTrade)
        barsSinceRedExit = barssince(alertBullish)
        barsSinceGreenEntry = barssince(startLongTrade)
        barsSinceGreenExit = barssince(alertBearish)
        isValidShortExit = barsSinceRedExit > barsSinceRedEntry
        isValidLongExit = barsSinceGreenExit > barsSinceGreenEntry
        endLongTradeDynamic = isBearishChange & pd.Series(isValidLongExit).shift(1)
        endShortTradeDynamic = isBullishChange & pd.Series(isValidShortExit).shift(1)

        # Fixed Exit Conditions: Booleans for ML Model Position Exits based on Bar-Count Filters
        endLongTradeStrict = ((isHeldFourBars & self.df["isLastSignalBuy"]) | (isHeldLessThanFourBars & self.df["isNewSellSignal"] & self.df["isLastSignalBuy"])) & startLongTrade.shift(4)
        endShortTradeStrict = ((isHeldFourBars & self.df["isLastSignalSell"]) | (isHeldLessThanFourBars & self.df["isNewBuySignal"] & self.df["isLastSignalSell"])) & startShortTrade.shift(4)
        isDynamicExitValid = ~useEmaFilter & ~useSmaFilter & ~useKernelSmoothing
        self.df["endLongTrade"] = self.settings.useDynamicExits & isDynamicExitValid & endLongTradeDynamic | endLongTradeStrict
        self.df["endShortTrade"] = self.settings.useDynamicExits & isDynamicExitValid & endShortTradeDynamic | endShortTradeStrict


    # =============================
    # ==== Dump or Return Data ====
    # =============================

    def dump(self, name: str):
        self.df.to_csv(name)


    def data(self) -> pd.DataFrame:
        return self.df


    # =========================
    # ====    Plotting     ====
    # =========================

    def plot(self, name: str):
        import mplfinance as mpf
        len = self.df.index.size

        # yhat1_g = [self.yhat1[v] if np.where(useKernelSmoothing, isBullishSmooth, isBullishRate)[v] else np.NaN for v in range(self.df.head(len).index.size)]
        # yhat1_r = [self.yhat1[v] if ~np.where(useKernelSmoothing, isBullishSmooth, isBullishRate)[v] else np.NaN for v in range(self.df.head(len).index.size)]
        sub_plots = [
            mpf.make_addplot(self.yhat1.head(len), ylabel="Kernel Regression Estimate", color='blue'),
            mpf.make_addplot(self.yhat2.head(len), ylabel="yhat2", color='gray'),
            mpf.make_addplot(self.df["startLongTrade"], ylabel="startLongTrade", color='green', type='scatter', markersize=50, marker='^'),
            mpf.make_addplot(self.df["startShortTrade"], ylabel="startShortTrade", color='red', type='scatter', markersize=50, marker='v'),
        ]
        s = mpf.make_mpf_style(base_mpf_style='yahoo', rc={'figure.facecolor': 'lightgray'}, edgecolor='black',
                            marketcolors=mpf.make_marketcolors(base_mpf_style='yahoo', inherit=True, alpha=0.2))
        fig, axlist = mpf.plot(self.df[['open', 'high', 'low', 'close']].head(len), type='candle', style=s, addplot=sub_plots, figsize=(20,20) ,returnfig=True)

        for x in range(len):
            y = self.df.loc[self.df.index[x], 'low']
            axlist[0].text(x, y, self.df.loc[self.df.index[x], "prediction"])

        fig.figure.savefig(fname=name)
