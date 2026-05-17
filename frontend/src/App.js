import "@/App.css";
import { BrowserRouter, Routes, Route, Navigate, useParams } from "react-router-dom";
import { Toaster } from "./components/ui/sonner";
import { Suspense, lazy } from "react";
import { WebSocketProvider } from "./context/WebSocketContext.jsx";
import { ActivePathProvider } from "./context/ActivePathContext.jsx"; // ETAP C
import { AdminAuthProvider } from "./context/AdminAuthContext.jsx";
import { AuthProvider } from "./context/AuthContext";
import AppLayout from "./layout/AppLayout";
import { useDashboard } from "./hooks/useDashboard";
import AdminProtectedRoute from "./components/AdminProtectedRoute";

// Loading component for Suspense fallback
const PageLoader = () => (
  <div className="min-h-screen bg-gray-50 flex items-center justify-center">
    <div className="flex flex-col items-center gap-4">
      <div className="w-10 h-10 border-4 border-gray-200 border-t-gray-900 rounded-full animate-spin" />
      <p className="text-sm text-gray-500 font-medium">Loading...</p>
    </div>
  </div>
);

// Lazy loaded pages - Code Splitting
// Critical pages (loaded immediately for fast initial render)
import MarketDiscovery from "./pages/MarketDiscovery";
import P0Dashboard from "./pages/P0Dashboard";

// Advanced v2 (loaded immediately)
import SystemOverview from "./pages/SystemOverview";
import MLHealth from "./pages/MLHealth";
import SignalsAttribution from "./pages/SignalsAttribution";

// Main navigation pages (lazy loaded)
const WalletSearchPage = lazy(() => import("./pages/OnchainV3/WalletSearchPage"));

// Redirect /wallet/:address → On-chain wallet tab
function WalletRedirect() {
  const { address } = useParams();
  return <Navigate to={`/intelligence/onchain-v3?tab=wallet&wallet=${encodeURIComponent(address || '')}`} replace />;
}
const EntitiesPage = lazy(() => import("./pages/EntitiesTerminal"));
const SignalsPage = lazy(() => import("./pages/SignalsIntelPage"));
const SignalDetailPage = lazy(() => import("./pages/SignalDetailPage"));
const WatchlistPage = lazy(() => import("./pages/WatchlistPage"));
// Alerts V2 - System & Intelligence Notifications (replaced legacy AlertsPage)
const AlertsPage = lazy(() => import("./pages/AlertsPageV2"));
const NotificationsPage = lazy(() => import("./pages/NotificationsPage"));
const SettingsPage = lazy(() => import("./pages/SettingsPage"));
const LandingPage = lazy(() => import("./pages/LandingPage"));
const LegalPage = lazy(() => import("./pages/LegalPage"));
const StrategiesPage = lazy(() => import("./pages/StrategiesPage"));
const ActorsPage = lazy(() => import("./pages/ActorsPage"));
const ActorsGraphPage = lazy(() => import("./pages/ActorsGraphPage"));
const ActorDetailPage = lazy(() => import("./pages/ActorDetailPage"));
const CorrelationPage = lazy(() => import("./pages/CorrelationPage"));
// PHASE 4.1: V2 UI Pages (replacing V1)
const EnginePage = lazy(() => import("./pages/EnginePageV2"));
const EngineDashboard = lazy(() => import("./pages/EngineDashboardV2"));
// Phase 13: Market Brain Engine — Unified Decision Intelligence
const MarketBrainEngine = lazy(() => import("./pages/MarketBrainEngine"));
// P0.2 - Registries Page (Token Registry + Address Labels)
const RegistriesPage = lazy(() => import("./pages/RegistriesPage"));
const RankingsDashboard = lazy(() => import("./pages/RankingsDashboardV2"));
const AttributionDashboard = lazy(() => import("./pages/AttributionDashboard"));
const MLReadyDashboard = lazy(() => import("./pages/MLReadyDashboard"));
// PHASE 4.2: Shadow Mode Dashboard
const ShadowModeDashboard = lazy(() => import("./pages/ShadowModeDashboard"));
// PHASE 4.3: Data Pipeline Monitoring
const DataPipelineMonitoring = lazy(() => import("./pages/DataPipelineMonitoring"));
const ShadowMLDashboard = lazy(() => import("./pages/ShadowMLDashboard"));

// Phase 4.6 - ML Intelligence Dashboard
const IntelligencePage = lazy(() => import("./components/IntelligencePage"));

// P1 - ML Monitoring Dashboard
const MLMonitoringPage = lazy(() => import("./pages/MLMonitoringPage"));

// P2.A - Confidence Dashboard
// REMOVED: ConfidenceDashboardPage (dead route → redirected to ML Overview)

// Admin Panel Pages
const AdminLoginPage = lazy(() => import("./pages/admin/AdminLoginPage"));
const AdminDashboardPage = lazy(() => import("./pages/admin/AdminDashboardPage"));
// REMOVED: AdminMLPage (dead → redirected to /admin/ml/overview)
// REMOVED: AdminMLOpsPage (dead route → redirected to ML Overview)
const AdminProvidersPage = lazy(() => import("./pages/admin/AdminProvidersPage"));
const AdminAuditPage = lazy(() => import("./pages/admin/AdminAuditPage"));
// Admin Profile — now a tab inside IntelAdminPage
// const AdminProfilePage = lazy(() => import("./pages/admin/AdminProfilePage"));
const SystemOverviewPage = lazy(() => import("./pages/admin/SystemOverviewPage"));
const DataPipelinesPage = lazy(() => import("./pages/admin/DataPipelinesPage"));
// Admin Settings — removed (dead code, no backend)
// const AdminSettingsPage = lazy(() => import("./pages/admin/AdminSettingsPage"));
const IntelAdminPage = lazy(() => import("./pages/admin/IntelAdminPage"));
const AdminBacktestingPage = lazy(() => import("./pages/admin/AdminBacktestingPage"));
const AdminValidationPage = lazy(() => import("./pages/admin/AdminValidationPage"));
// REMOVED: AdminMLAccuracyPage (dead route → redirected to ML Overview)
// REMOVED: AdminRetrainPage (dead route → redirected to Auto-Retrain)
// ML v2.3 - Auto-Retrain Policies + Feature Analysis
const AdminAutoRetrainPage = lazy(() => import("./pages/admin/AdminAutoRetrainPage"));
// REMOVED: AdminMLFeaturesPage (dead route → redirected to Models)
// ML Governance - Approvals
const AdminApprovalsPage = lazy(() => import("./pages/admin/AdminApprovalsPage"));
// D4 - Indexer Control Panel
const IndexerPage = lazy(() => import("./pages/admin/IndexerPage"));

// News Admin — Parser, Sources, Health, Events
const NewsAdminPage = lazy(() => import("./pages/admin/NewsAdminPage"));

// On-chain Admin — Unified Control Page (6 tabs)
const AdminOnchainPage = lazy(() => import("./pages/admin/onchain/AdminOnchainPage"));

// Product Signals - Alerts Settings
// Admin Alerts — now handled by unified AdminSignalsPage
// const AdminAlertsSettingsPage = lazy(() => import("./pages/admin/AdminAlertsSettingsPage"));

// FOMO Alerts Admin (Full Control)
// FOMO Alerts — now handled by unified AdminSignalsPage
// const FomoAlertsAdminPage = lazy(() => import("./pages/admin/FomoAlertsAdminPage"));

// Predictions Admin — Self-Improvement Engine (Tuning)
const AdminPredictionTuningPage = lazy(() => import("./pages/admin/AdminPredictionTuningPage"));

// Admin Billing Console — single unified page with internal tabs
const BillingAdminPage = lazy(() => import("./pages/admin/BillingAdminPage"));
const MiniAppAdminPage = lazy(() => import("./pages/admin/MiniAppAdminPage"));
const AdminReferralsPage = lazy(() => import("./pages/admin/AdminReferralsPage"));
const ReferralLandingPage = lazy(() => import("./pages/ReferralLandingPage"));

// Twitter Intelligence Overview (War Room)
const TwitterOverviewPage = lazy(() => import("./pages/twitter/TwitterOverviewPage"));

// Fractal Intelligence — Single entry point (like Exchange/Twitter)
const FractalIntelligencePage = lazy(() => import("./pages/FractalIntelligencePage"));
const FractalAdminPage = lazy(() => import("./pages/FractalAdminPage"));
const CombinedTerminalPage = lazy(() => import("./pages/CombinedTerminalPage"));

// Twitter Intelligence — Main Module Page (like OnchainV3)
const TwitterPage = lazy(() => import("./pages/twitter/TwitterPage"));

// Twitter Parser Admin v4.0
const TwitterParserAccountsPage = lazy(() => import("./pages/admin/TwitterParserAccountsPage"));
const TwitterParserSessionsPage = lazy(() => import("./pages/admin/TwitterParserSessionsPage"));
const TwitterParserSlotsPage = lazy(() => import("./pages/admin/TwitterParserSlotsPage"));
const TwitterParserMonitorPage = lazy(() => import("./pages/admin/TwitterParserMonitorPage"));

// A.3 - Admin Control Plane (Twitter Users)
const AdminTwitterPage = lazy(() => import("./pages/admin/twitter/AdminTwitterPage"));
const AdminUserDetailPage = lazy(() => import("./pages/admin/twitter/AdminUserDetailPage"));
const AdminPoliciesPage = lazy(() => import("./pages/admin/twitter/AdminPoliciesPage"));
// Phase 7.1 - Admin System Control Panel (enhanced)
const AdminSystemControlPage = lazy(() => import("./pages/admin/twitter/AdminSystemControlPage"));
const AdminLoadTestPage = lazy(() => import("./pages/admin/twitter/AdminLoadTestPage"));
const AdminConsentPoliciesPage = lazy(() => import("./pages/admin/twitter/AdminConsentPoliciesPage"));

// Twitter Admin — Unified Control Page (5 tabs)
const AdminTwitterUnifiedPage = lazy(() => import("./pages/admin/twitter-unified/AdminTwitterUnifiedPage"));

// Connections Admin
const AdminConnectionsPage = lazy(() => import("./pages/admin/AdminConnectionsPage"));

// B4 - User-Facing Parser UI
const ParserOverviewPage = lazy(() => import("./pages/dashboard/parser/ParserOverviewPage"));

// P4.1 - Twitter Integration (User-Owned Accounts)
const TwitterIntegrationPage = lazy(() => import("./pages/dashboard/twitter/TwitterIntegrationPage"));
const TwitterTargetsPage = lazy(() => import("./pages/dashboard/twitter/TwitterTargetsPage"));

// P4.1 - Notification Settings
const NotificationsSettingsPage = lazy(() => import("./pages/settings/NotificationsSettingsPage"));

// Settings - API Keys
const ApiKeysSettingsPage = lazy(() => import("./pages/settings/ApiKeysSettingsPage"));

// A1 - Admin ML & Signals Pages
const AdminSignalsPage = lazy(() => import("./pages/admin/AdminSignalsPage"));
const AdminModelRegistryPage = lazy(() => import("./pages/admin/AdminModelRegistryPage"));
const AdminResearchPage = lazy(() => import("./pages/admin/AdminResearchPage"));
// REMOVED: Individual research pages consolidated into AdminResearchPage

// P1.8 - Graph Intelligence Page
const GraphIntelligencePage = lazy(() => import("./pages/GraphIntelligencePage"));

// DEPRECATED: WalletExplorerPage removed in Wallet v2

// P1 - Market Signals Dashboard
const MarketSignalsPage = lazy(() => import("./pages/MarketSignalsPage"));

// S3.7 - Classic Sentiment Analyzer (URL-first)
const SentimentPage = lazy(() => import("./pages/SentimentPage"));

// Telegram Intelligence Module (Plugin - isolated)
const TelegramEntitiesPage = lazy(() => import("./pages/TelegramEntitiesPage"));
const TelegramChannelOverviewPage = lazy(() => import("./pages/TelegramChannelOverviewPage"));
// TelegramNetworkPage removed per user request
const TelegramFeedPage = lazy(() => import("./pages/TelegramFeedPage"));

// S3.9 - Twitter Feed (Sentiment без цены)
const TwitterFeedPage = lazy(() => import("./pages/TwitterSentimentPage"));

// S5 - Twitter AI (Sentiment × Price)
const TwitterAIPage = lazy(() => import("./pages/TwitterAIPage"));

// Sentiment Admin — 3-layer architecture + API Console
const AdminSentimentPage = lazy(() => import("./pages/admin/AdminSentimentPage"));
const AdminSentimentResearchPage = lazy(() => import("./pages/admin/AdminSentimentResearchPage"));
const AdminSentimentApiPage = lazy(() => import("./pages/admin/AdminSentimentApiPage"));

// Module Control Centers (Institutional-grade Admin)
const SentimentModuleAdminPage = lazy(() => import("./pages/admin/modules/sentiment"));
const OnchainModuleAdminPage = lazy(() => import("./pages/admin/modules/onchain"));

// Sentiment Data Accumulation Monitor
const SentimentDataMonitorPage = lazy(() => import("./pages/admin/modules/sentiment/SentimentDataMonitorPage"));

// S6.4 - Observation Model Admin Dashboard
const AdminObservationPage = lazy(() => import("./pages/admin/AdminObservationPage"));

// S7 - Onchain Validation Admin Dashboard
const AdminOnchainValidationPage = lazy(() => import("./pages/admin/AdminOnchainValidationPage"));

// ON-CHAIN V3 - New Architecture
const OnchainV3Page = lazy(() => import("./pages/OnchainV3/OnchainV3Page"));

// Phase 2: Wallet Intelligence Page
const WalletPage = lazy(() => import("./pages/OnchainV3/WalletPage"));

// S8 - Meta-Brain Admin Dashboard
const AdminMetaBrainPage = lazy(() => import("./pages/admin/AdminMetaBrainPage"));

// S4.ADM - ML Admin Control Layer
const AdminMLOverviewPage = lazy(() => import("./pages/admin/AdminMLOverviewPage"));
const AdminTwitterControlPage = lazy(() => import("./pages/admin/AdminTwitterPage"));
// REMOVED: AdminAutomationPage (dead route → redirected to ML Overview)

// U1.2 - Market Signals A-F Cards
const MarketSignalsU12Page = lazy(() => import("./modules/market/MarketSignalsPage"));

// FREEZE v2.3 - Unified Market Hub
const MarketHub = lazy(() => import("./pages/MarketHub"));

// S1.4 - User Strategies Page
const MarketStrategiesPage = lazy(() => import("./pages/MarketStrategiesPage"));

// S10.1 - Exchange Intelligence
const ExchangeOverviewPage = lazy(() => import("./pages/ExchangeOverviewPage"));
// AdminExchangePage (S10.1) removed — merged into AdminExchangeControlPage

// Exchange Intelligence — Single entry point (like Twitter)
const ExchangePage = lazy(() => import("./pages/ExchangePage"));

// Exchange Dashboard (used as Overview tab inside ExchangePage)
const ExchangeDashboardPage = lazy(() => import("./pages/ExchangeDashboardPage"));

// Y2 - Exchange Admin Control Page (Providers + Jobs)
const AdminExchangeControlPage = lazy(() => import("./pages/admin/AdminExchangeControlPage"));
const IntelligenceConsolePage = lazy(() => import("./pages/admin/IntelligenceConsolePage"));

// Admin Exchange Wrapper (for all Exchange pages in Admin)
const AdminExchangeWrapper = lazy(() => import("./pages/admin/AdminExchangeWrapper"));

// Decision Intelligence Dashboard (DashboardPack V1)
const DecisionIntelPage = lazy(() => import("./pages/admin/modules/exchange/DecisionIntelPage"));

// Overview Engine Admin Config
const AdminOverviewEnginePage = lazy(() => import("./pages/admin/AdminOverviewEnginePage"));

// Phase 1.2 - Market Product Pages
const MarketAssetPage = lazy(() => import("./pages/market/MarketAssetPage"));

// S10.2 - Order Flow Intelligence
const OrderFlowPage = lazy(() => import("./pages/OrderFlowPage"));

// S10.3 - Volume & OI Regimes
const VolumeOIPage = lazy(() => import("./pages/VolumeOIPage"));

// S10.4 - Liquidation Cascades
const LiquidationsPage = lazy(() => import("./pages/LiquidationsPage"));

// S10.5 - Exchange Patterns
const PatternsPage = lazy(() => import("./pages/PatternsPage"));

// S10.6 - Exchange Labs (Dataset)
const LabsPage = lazy(() => import("./pages/LabsPage"));

// Exchange Research Page (Hypotheses & Interpretations)
const ExchangeResearchPage = lazy(() => import("./pages/ExchangeResearchPage"));

// Intelligence Pages
const MetaBrainPage = lazy(() => import("./pages/MetaBrainPage"));
const OnchainValidationPage = lazy(() => import("./pages/OnchainValidationPage"));

// Labs v3 - 18 Canonical Labs
const LabsPageV3 = lazy(() => import("./pages/LabsPageV3"));

// S10.6I.8 - Indicators Explorer
const IndicatorsExplorerPage = lazy(() => import("./pages/IndicatorsExplorerPage"));

// S10.LABS-01 - Regime Forward Outcome
const LabsRegimeForwardPage = lazy(() => import("./pages/LabsRegimeForwardPage"));

// S10.LABS-02 - Regime Attribution
const LabsRegimeAttributionPage = lazy(() => import("./pages/LabsRegimeAttributionPage"));

// S10.LABS-03 - Pattern Risk
const LabsPatternRiskPage = lazy(() => import("./pages/LabsPatternRiskPage"));

// S10.LABS-04 - Sentiment Interaction
const LabsSentimentInteractionPage = lazy(() => import("./pages/LabsSentimentInteractionPage"));

// S10.W - Whale Intelligence Pages
const WhalePatternsPage = lazy(() => import("./pages/WhalePatternsPage"));
const WhaleStatePage = lazy(() => import("./pages/WhaleStatePage"));
const LabsWhaleRiskPage = lazy(() => import("./pages/LabsWhaleRiskPage"));

// Macro Regime - Market Intelligence
const LabsMacroRegimePage = lazy(() => import("./pages/Exchange/LabsMacroRegimePage"));

// BLOCK 5-6: Exchange Segments Test Page - REMOVED (integrated into PriceExpectationV2Page)

// C1 - Alignment Explorer (Exchange × Sentiment Fusion)
const AlignmentExplorerPage = lazy(() => import("./pages/AlignmentExplorerPage"));

// B2 + B4 - Exchange Markets & Verdicts
const ExchangeMarketsPage = lazy(() => import("./pages/ExchangeMarketsPage"));

// Alt Radar - Altcoin Opportunity Scanner (Blocks 1-28)
const AltRadarPage = lazy(() => import("./pages/AltRadarPage"));

// Alt Screener - ML-powered Pattern Matching (Block 1.6)
const AltScreenerPage = lazy(() => import("./pages/AltScreenerPage"));

// Alt Movers - Cluster-based Rotation Candidates (Block 2.14)
const AltMoversPage = lazy(() => import("./pages/AltMoversPage"));

// S10.7.4 - Exchange ML Admin
const MLAdminPage = lazy(() => import("./pages/MLAdminPage"));

// FOMO AI - Main Product (Phase 5 UI)
const FomoAiPage = lazy(() => import("./pages/fomo-ai/FomoAiPage"));

// Snapshot Page (Public Share Links)
const SnapshotPage = lazy(() => import("./pages/snapshot/SnapshotPage"));

// MLOps Dashboard (Phase 5 - Model Management)
const MLOpsPage = lazy(() => import("./pages/mlops/MLOpsPage"));

// MLOps Promotion Page (ML Model Promotion & Control)
const MLOpsPromotionPage = lazy(() => import("./pages/Intelligence/MLOpsPromotionPage"));

// Price vs Expectation Page (Central Chart - Price vs Prediction)
const PriceExpectationPage = lazy(() => import("./pages/Intelligence/PriceExpectationPage"));

// Price vs Expectation V2 Page (New Forecast System)
const PriceExpectationV2Page = lazy(() => import("./pages/Intelligence/PriceExpectationV2Page"));
const PredictionMarketsPage = lazy(() => import("./pages/PredictionMarketsPage"));

// Connections Module Pages (Layer 2 Analytics - OSINT Dashboard)
const ConnectionsPage = lazy(() => import("./pages/connections/ConnectionsPage"));
const ConnectionsInfluencersPage = lazy(() => import("./pages/connections/ConnectionsInfluencersPage"));
const InfluencerDetailPage = lazy(() => import("./pages/connections/InfluencerDetailPage"));
const ConnectionsUnifiedPage = lazy(() => import("./pages/connections/ConnectionsUnifiedPage"));

const ClusterAttentionPage = lazy(() => import("./pages/connections/ClusterAttentionPage"));
const AltSeasonPage = lazy(() => import("./pages/connections/AltSeasonPage"));
const RealityLeaderboardPage = lazy(() => import("./pages/connections/Reality/RealityLeaderboardPage"));
const ConnectionsEarlySignalPage = lazy(() => import("./pages/connections/ConnectionsEarlySignalPage"));
// ConnectionsBackersPage removed — obsolete
const BackerDetailPage = lazy(() => import("./pages/connections/BackerDetailPage"));
const BakeryPage = lazy(() => import("./pages/connections/BakeryPage"));
const BakerDetailPage = lazy(() => import("./pages/connections/BakerDetailPage"));
const LifecyclePage = lazy(() => import("./pages/connections/LifecyclePage"));
const NarrativesPage = lazy(() => import("./pages/connections/NarrativesPage"));
const FarmNetworkPage = lazy(() => import("./pages/connections/FarmNetworkPage"));
const StrategySimulationPage = lazy(() => import("./pages/connections/StrategySimulationPage"));
const ConnectionsWatchlistPage = lazy(() => import("./pages/connections/WatchlistPage"));
const ConnectionsDetailPage = lazy(() => import("./pages/connections/ConnectionsDetailPage"));

// P2.4.3 - Graph Share Page (standalone, no layout)
const GraphSharePage = lazy(() => import("./pages/share/GraphSharePage"));

// Legal Pages (Chrome Extension Privacy Policy - required for Chrome Web Store)
const ChromeExtensionPrivacyPage = lazy(() => import("./pages/legal/ChromeExtensionPrivacyPage"));

// Token Pages - NEW CANONICAL ROUTING ARCHITECTURE
// Alias route: /token/:symbol → resolves to canonical
// Canonical route: /token/:chainId/:address → source of truth
const TokenAliasResolver = lazy(() => import("./pages/TokenAliasResolver"));
const TokenCanonicalPage = lazy(() => import("./pages/TokenCanonicalPage"));

// Telegram Mini App — Decision Delivery Layer (standalone, no layout)
const TelegramMiniAppPage = lazy(() => import("./pages/TelegramMiniAppPage"));

// RESTORED 2026-05-16: Tech Analysis web page (drop-in from F-TRADE-FINAL@204f84a).
const TechAnalysisPage = lazy(() => import("./pages/TechAnalysis"));
const TerminalWorkspacePage = lazy(() => import("./pages/Terminal"));
const TradingTerminalPage = lazy(() => import("./pages/Trading"));
const CognitiveTerminalPage = lazy(() => import("./pages/CognitiveTerminalPage"));
const TradingPortfolioPage = lazy(() => import("./pages/TradingPortfolioPage"));
const AdminTechAnalysisPage = lazy(() => import("./pages/admin/AdminTechAnalysisPage"));

// Detail pages (lazy loaded - less frequently accessed)
const TokenDetail = lazy(() => import("./pages/TokenDetailRefactored"));
const Portfolio = lazy(() => import("./pages/Portfolio"));
const EntityDetail = lazy(() => import("./pages/EntityTerminal"));
const SignalSnapshot = lazy(() => import("./pages/SignalSnapshot"));
const ActorProfile = lazy(() => import("./pages/ActorProfile"));

function App() {
  const { data } = useDashboard(1, 1); // Fetch only for globalState

  return (
    <WebSocketProvider>
      <ActivePathProvider>
        <AdminAuthProvider>
        <BrowserRouter>
        <AuthProvider>
          <Suspense fallback={<PageLoader />}>
            <Routes>
              {/* Admin Panel Routes (standalone, no main layout) */}
              <Route path="/admin/login" element={<AdminLoginPage />} />

              {/* Telegram Mini App — standalone, no layout wrapper */}
              <Route path="/miniapp" element={<TelegramMiniAppPage />} />

              {/* Protected Admin Routes */}
              <Route element={<AdminProtectedRoute />}>
                <Route path="/admin/dashboard" element={<Navigate to="/admin/onchain" replace />} />
                <Route path="/admin" element={<Navigate to="/admin/billing" replace />} />

                {/* On-chain Admin — Unified Control Page (6 tabs) */}
                <Route path="/admin/onchain" element={<AdminOnchainPage />} />
                <Route path="/admin/system-overview" element={<SystemOverviewPage />} />
                <Route path="/admin/data-pipelines" element={<Navigate to="/admin/onchain?tab=infrastructure" replace />} />
                {/* Settings — removed, dead code */}
                <Route path="/admin/settings" element={<Navigate to="/admin/intel" replace />} />
                <Route path="/admin/billing" element={<BillingAdminPage />} />
                <Route path="/admin/miniapp" element={<MiniAppAdminPage />} />
                <Route path="/admin/referrals" element={<AdminReferralsPage />} />
                <Route path="/admin/intel" element={<IntelAdminPage />} />
                <Route path="/admin/backtesting" element={<AdminBacktestingPage />} />
                {/* Validation removed — functionality covered by MetaBrain Drift */}
                <Route path="/admin/ml-accuracy" element={<Navigate to="/admin/ml/overview" replace />} />
                <Route path="/admin/retrain" element={<Navigate to="/admin/auto-retrain" replace />} />
                <Route path="/admin/auto-retrain" element={<AdminAutoRetrainPage />} />
                <Route path="/admin/ml-features" element={<Navigate to="/admin/ml/research" replace />} />
                <Route path="/admin/ml/approvals" element={<AdminApprovalsPage />} />
                <Route path="/admin/indexer" element={<Navigate to="/admin/onchain?tab=infrastructure" replace />} />
              
              {/* MLOps — redirected to ML Overview */}
              <Route path="/admin/mlops" element={<Navigate to="/admin/ml/overview" replace />} />
              
              {/* Product Signals - redirected to unified Signals page */}
              <Route path="/admin/alerts" element={<Navigate to="/admin/signals?tab=alerts" replace />} />
              
              {/* FOMO Alerts - redirected to unified Signals page */}
              <Route path="/admin/fomo-alerts" element={<Navigate to="/admin/signals?tab=fomo" replace />} />
              
              {/* Confidence — redirected to ML Overview */}
              <Route path="/admin/metrics/confidence" element={<Navigate to="/admin/ml/overview" replace />} />
              
              {/* Twitter Parser Admin v4.0 */}
              {/* Twitter Admin — Unified Control Page (5 tabs) */}
              <Route path="/admin/twitter-admin" element={<AdminTwitterUnifiedPage />} />

              {/* Twitter Parser — НЕ ТРОГАЕМ, production infrastructure */}
              <Route path="/admin/twitter-parser/accounts" element={<TwitterParserAccountsPage />} />
              <Route path="/admin/twitter-parser/sessions" element={<TwitterParserSessionsPage />} />
              <Route path="/admin/twitter-parser/slots" element={<TwitterParserSlotsPage />} />
              <Route path="/admin/twitter-parser/monitor" element={<TwitterParserMonitorPage />} />
              
              {/* Twitter Users / Policies (legacy detail pages) */}
              <Route path="/admin/twitter" element={<Navigate to="/admin/twitter-admin" replace />} />
              <Route path="/admin/twitter/users/:userId" element={<AdminUserDetailPage />} />
              <Route path="/admin/twitter/policies" element={<AdminPoliciesPage />} />
              <Route path="/admin/twitter/consent-policies" element={<AdminConsentPoliciesPage />} />
              <Route path="/admin/twitter/system" element={<AdminSystemControlPage />} />
              <Route path="/admin/twitter/system-legacy" element={<Navigate to="/admin/twitter-admin" replace />} />
              <Route path="/admin/twitter/performance" element={<AdminLoadTestPage />} />
              
              {/* Connections Admin */}
              <Route path="/admin/connections" element={<AdminConnectionsPage />} />

              {/* News Admin */}
              <Route path="/admin/news" element={<NewsAdminPage />} />

              {/* System Parsing — удалён (дубль Parser) → redirect */}
              <Route path="/admin/system-parsing" element={<Navigate to="/admin/twitter-admin?tab=parser" replace />} />
              <Route path="/admin/system-parsing/*" element={<Navigate to="/admin/twitter-admin?tab=parser" replace />} />
              
              {/* A1 - Admin ML & Signals */}
              <Route path="/admin/signals" element={<AdminSignalsPage />} />
              <Route path="/admin/ml/signals" element={<AdminSignalsPage />} />
              <Route path="/admin/ml/research" element={<AdminResearchPage />} />
              <Route path="/admin/ml/models" element={<AdminModelRegistryPage />} />
              <Route path="/admin/ml/datasets" element={<Navigate to="/admin/ml/research" replace />} />
              <Route path="/admin/ml/ablation" element={<Navigate to="/admin/ml/research" replace />} />
              <Route path="/admin/ml/stability" element={<Navigate to="/admin/ml/research" replace />} />
              <Route path="/admin/ml/attribution" element={<Navigate to="/admin/ml/research" replace />} />
              
              {/* Sentiment — 3-layer architecture + API Console */}
              <Route path="/admin/sentiment-api" element={<AdminSentimentApiPage />} />
              <Route path="/admin/sentiment" element={<AdminSentimentPage />} />
              <Route path="/admin/sentiment/reliability" element={<SentimentModuleAdminPage />} />
              <Route path="/admin/sentiment/research" element={<AdminSentimentResearchPage />} />
              <Route path="/admin/sentiment/data-monitor" element={<SentimentDataMonitorPage />} />
              
              {/* Module Control Centers (Institutional-grade) */}
              <Route path="/admin/modules/onchain" element={<Navigate to="/admin/onchain?tab=governance" replace />} />

              {/* Predictions Admin — Self-Improvement Tuning */}
              <Route path="/admin/predictions/tuning" element={<AdminPredictionTuningPage />} />
              <Route path="/admin/fractal" element={
                <Suspense fallback={<PageLoader />}>
                  <FractalAdminPage />
                </Suspense>
              } />
              
              {/* S6.4 - Observation Model → redirected to On-chain Research */}
              <Route path="/admin/ml/observation" element={<Navigate to="/admin/onchain?tab=research" replace />} />
              
              {/* S7 - Onchain Validation → redirected to On-chain Validation */}
              <Route path="/admin/ml/onchain-validation" element={<Navigate to="/admin/onchain?tab=validation" replace />} />
              
              {/* S8 - Meta-Brain Admin Dashboard */}
              <Route path="/admin/ml/meta-brain" element={<AdminMetaBrainPage />} />
              
              {/* S4.ADM - ML Admin Control Layer (standalone Admin Layout) */}
              <Route path="/admin/ml/overview" element={<AdminMLOverviewPage />} />
              <Route path="/admin/ml/twitter-control" element={<Navigate to="/admin/twitter-admin?tab=ml" replace />} />
              <Route path="/admin/ml/automation" element={<Navigate to="/admin/ml/overview" replace />} />
              
              {/* S10.1 - Exchange Admin */}
              <Route path="/admin/exchange" element={<AdminExchangeControlPage />} />

              {/* RESTORED 2026-05-16: Admin Tech Analysis (drop-in from F-TRADE-FINAL@204f84a) */}
              <Route path="/admin/tech-analysis" element={<AdminTechAnalysisPage />} />
              <Route path="/admin/trading" element={<Navigate to="/admin/tech-analysis" replace />} />
              <Route path="/admin/trading-terminal" element={<Navigate to="/admin/tech-analysis" replace />} />
              
              {/* Intelligence Console (Block 4+6 Dashboard) */}
              <Route path="/admin/exchange/intelligence" element={<IntelligenceConsolePage />} />
              
              {/* Decision Intelligence (DashboardPack V1) */}
              <Route path="/admin/exchange/decision-intel" element={<DecisionIntelPage />} />
              
              {/* Overview Engine Config (Decision thresholds, freeze) */}
              <Route path="/admin/overview-engine" element={<AdminOverviewEnginePage />} />
              
              {/* Y2 - Exchange Admin Control (Providers + Jobs) */}
              <Route path="/admin/exchange/control" element={<AdminExchangeControlPage />} />
              
              {/* ML Admin (wrapped in AdminLayout) */}
              <Route path="/admin/exchange/ml" element={<AdminExchangeWrapper />} />
              
              {/* Exchange Data Pages in Admin */}
              <Route path="/admin/exchange/data/overview" element={<AdminExchangeWrapper />} />
              <Route path="/admin/exchange/data/markets" element={<AdminExchangeWrapper />} />
              <Route path="/admin/exchange/data/orderflow" element={<AdminExchangeWrapper />} />
              <Route path="/admin/exchange/data/volume" element={<AdminExchangeWrapper />} />
              <Route path="/admin/exchange/data/indicators" element={<AdminExchangeWrapper />} />
              
              {/* Exchange Signals Pages in Admin */}
              <Route path="/admin/exchange/signals/liquidations" element={<AdminExchangeWrapper />} />
              <Route path="/admin/exchange/signals/patterns" element={<AdminExchangeWrapper />} />
              
              {/* Exchange Labs Pages in Admin */}
              <Route path="/admin/exchange/labs" element={<AdminExchangeWrapper />} />
              <Route path="/admin/exchange/labs/regime-forward" element={<AdminExchangeWrapper />} />
              <Route path="/admin/exchange/labs/regime-attribution" element={<AdminExchangeWrapper />} />
              <Route path="/admin/exchange/labs/pattern-risk" element={<AdminExchangeWrapper />} />
              <Route path="/admin/exchange/labs/sentiment" element={<AdminExchangeWrapper />} />
              <Route path="/admin/exchange/labs/whale-risk" element={<AdminExchangeWrapper />} />
              <Route path="/admin/exchange/labs/alignment" element={<AdminExchangeWrapper />} />
              
              {/* Exchange Whale Pages in Admin */}
              <Route path="/admin/exchange/whales/patterns" element={<AdminExchangeWrapper />} />
              <Route path="/admin/exchange/whales/state" element={<AdminExchangeWrapper />} />
              
              <Route path="/admin/ml" element={<Navigate to="/admin/ml/overview" replace />} />
              <Route path="/admin/providers" element={<Navigate to="/admin/onchain?tab=infrastructure" replace />} />
              <Route path="/admin/audit" element={<AdminAuditPage />} />
              {/* Profile — now a tab in Intel System */}
              <Route path="/admin/profile" element={<Navigate to="/admin/intel?tab=profile" replace />} />
            </Route> {/* End of AdminProtectedRoute */}
              
              {/* P2.4.3: Standalone share page (no layout) */}
              <Route path="/share/graph/:shareId" element={<GraphSharePage />} />
              
              {/* Snapshot Page (Public Share Links - standalone, no layout) */}
              <Route path="/snapshot/:id" element={<SnapshotPage />} />
              
              {/* Legal Pages (Chrome Web Store compliance) */}
              <Route path="/privacy/chrome-extension" element={<ChromeExtensionPrivacyPage />} />
              
              {/* Landing Page (standalone — no sidebar) */}
              <Route path="/info" element={<LandingPage />} />
              <Route path="/ref/:code" element={<ReferralLandingPage />} />
              <Route path="/legal/:pageType" element={<LegalPage />} />
              
              {/* DECOMMISSIONED: Market sub-routes redirect to Onchain Intelligence */}
              <Route path="/market/signals/:asset" element={<Navigate to="/intelligence/onchain-v3?tab=signals" replace />} />
              <Route path="/market/signals" element={<Navigate to="/intelligence/onchain-v3?tab=signals" replace />} />
              <Route path="/market/strategies/:network" element={<Navigate to="/intelligence/onchain-v3" replace />} />
              <Route path="/market/strategies" element={<Navigate to="/intelligence/onchain-v3" replace />} />
              
              <Route element={<AppLayout />}>
                {/* Main Navigation */}
                {/* PREDICTION — Now the default landing page */}
                <Route path="/" element={<PriceExpectationV2Page />} />
                {/* DECOMMISSIONED: Intelligence Dashboard → Onchain v3 Overview */}
              <Route path="/intelligence/dashboard" element={<Navigate to="/intelligence/onchain-v3" replace />} />
                
              {/* FOMO AI - Main Product */}
              <Route path="/fomo-ai" element={<FomoAiPage />} />
              <Route path="/fomo-ai/:symbol" element={<FomoAiPage />} />
              
              {/* MLOps Dashboard */}
              <Route path="/mlops" element={<MLOpsPage />} />
              
              {/* MLOps Promotion - Model Control */}
              <Route path="/intelligence/mlops/promotion" element={<MLOpsPromotionPage />} />
              
              {/* DECOMMISSIONED: Old Market Hub redirects to Onchain Intelligence */}
              <Route path="/market" element={<Navigate to="/intelligence/onchain-v3" replace />} />
              <Route path="/market-signals" element={<Navigate to="/intelligence/onchain-v3?tab=signals" replace />} />
              {/* DECOMMISSIONED: Tokens → Assets tab in Onchain v3 */}
              <Route path="/tokens" element={<Navigate to="/intelligence/onchain-v3?tab=assets" replace />} />
              <Route path="/wallets" element={<Navigate to="/wallet" replace />} />
              <Route path="/entities" element={<EntitiesPage />} />
              <Route path="/signals" element={<SignalsPage />} />
              <Route path="/signals/:id" element={<SignalDetailPage />} />
              <Route path="/watchlist" element={<WatchlistPage />} />
              <Route path="/alerts" element={<AlertsPage />} />
              <Route path="/notifications" element={<NotificationsPage />} />
              <Route path="/settings" element={<SettingsPage />} />
              <Route path="/checkout" element={<Navigate to="/settings?tab=billing" replace />} />
              <Route path="/strategies" element={<StrategiesPage />} />
              <Route path="/actors" element={<ActorsPage />} />
              <Route path="/actors/graph" element={<ActorsGraphPage />} />
              <Route path="/actors/correlation" element={<CorrelationPage />} />
              <Route path="/actors/:actorId" element={<ActorDetailPage />} />
              <Route path="/engine" element={<EnginePage />} />
              <Route path="/engine/dashboard" element={<EngineDashboard />} />
              <Route path="/engine/brain" element={<MarketBrainEngine />} />
              <Route path="/shadow" element={<ShadowModeDashboard />} />
              <Route path="/pipeline" element={<DataPipelineMonitoring />} />
              <Route path="/registries" element={<RegistriesPage />} />
              <Route path="/rankings" element={<RankingsDashboard />} />
              <Route path="/attribution" element={<AttributionDashboard />} />
              <Route path="/ml-ready" element={<MLReadyDashboard />} />
              <Route path="/shadow-ml" element={<ShadowMLDashboard />} />
              
              {/* ═══════════════════════════════════════════════════════════
                  EXCHANGE v3 — Analytics + Labs (instruments returned!)
                  - Dashboard: Market state overview
                  - Market: Price, volume, OI, funding
                  - Signals: Raw exchange signals
                  - Research: Interpretations/hypotheses
                  - Labs: Individual analysis tools
                  ═══════════════════════════════════════════════════════════ */}
              <Route path="/exchange" element={<ExchangePage />} />
              {/* Legacy routes redirect to tabs */}
              <Route path="/exchange/markets" element={<ExchangePage />} />
              <Route path="/exchange/signals" element={<ExchangePage />} />
              <Route path="/exchange/research" element={<ExchangePage />} />
              <Route path="/exchange/labs" element={<ExchangePage />} />
              
              {/* Legacy Exchange routes (kept for backward compatibility) */}
              <Route path="/exchange/orderflow" element={<OrderFlowPage />} />
              <Route path="/exchange/volume" element={<VolumeOIPage />} />
              <Route path="/exchange/liquidations" element={<LiquidationsPage />} />
              <Route path="/exchange/patterns" element={<PatternsPage />} />
              <Route path="/exchange/labs/regime-forward" element={<LabsRegimeForwardPage />} />
              <Route path="/exchange/labs/regime-attribution" element={<LabsRegimeAttributionPage />} />
              <Route path="/exchange/labs/pattern-risk" element={<LabsPatternRiskPage />} />
              <Route path="/exchange/labs/sentiment-interaction" element={<LabsSentimentInteractionPage />} />
              <Route path="/exchange/labs/whale-risk" element={<LabsWhaleRiskPage />} />
              
              {/* Macro Regime - Market Intelligence */}
              <Route path="/exchange/labs/macro-regime" element={<ExchangePage />} />
              
              {/* C1 - Alignment Explorer (Exchange × Sentiment Fusion) */}
              <Route path="/exchange/labs/alignment" element={<AlignmentExplorerPage />} />
              
              {/* S10.W - Whale Intelligence */}
              <Route path="/exchange/whales/patterns" element={<WhalePatternsPage />} />
              <Route path="/exchange/whales/state" element={<WhaleStatePage />} />
              
              {/* S10.6I.8 - Indicators Explorer */}
              <Route path="/exchange/indicators" element={<IndicatorsExplorerPage />} />
              
              {/* S10.7.4 - Exchange ML Admin */}
              <Route path="/admin/exchange/ml" element={<MLAdminPage />} />
              
              {/* BLOCK 5-6: Exchange Segments - integrated into PriceExpectationV2Page */}
              
              {/* ═══════════════════════════════════════════════════════════
                  ALT RADAR — Altcoin Opportunity Scanner (Blocks 1-28)
                  ═══════════════════════════════════════════════════════════ */}
              <Route path="/exchange/alt-radar" element={<ExchangePage />} />
              
              {/* ═══════════════════════════════════════════════════════════
                  ALT SCREENER — ML Pattern Matching (Block 1.6)
                  ═══════════════════════════════════════════════════════════ */}
              <Route path="/exchange/alt-screener" element={<AltScreenerPage />} />
              <Route path="/market/alts" element={<AltScreenerPage />} />
              
              {/* ═══════════════════════════════════════════════════════════
                  ALT MOVERS — Cluster Rotation Candidates (Block 2.14)
                  ═══════════════════════════════════════════════════════════ */}
              <Route path="/market/alt-movers" element={<AltMoversPage />} />
              
              {/* ═══════════════════════════════════════════════════════════
                  INTELLIGENCE v3 — Brain/ML/Control (cleaned)
                  - Dashboard: System health
                  - MLOps: Model lifecycle
                  - Meta-Brain: Decision orchestration
                  - On-chain Validation: Signal verification
                  ═══════════════════════════════════════════════════════════ */}
              <Route path="/intelligence" element={<IntelligencePage />} />
              {/* MetaBrain merged into Prediction/Forecast tab */}
              <Route path="/intelligence/metabrain" element={<Navigate to="/intelligence/price-expectation-v2" replace />} />
              <Route path="/meta-brain" element={<Navigate to="/intelligence/price-expectation-v2" replace />} />
              {/* DECOMMISSIONED: Validation → Engine Diagnostics */}
              <Route path="/intelligence/onchain" element={<Navigate to="/intelligence/onchain-v3?tab=engine" replace />} />
              <Route path="/intelligence/price-expectation" element={<PriceExpectationPage />} />
              <Route path="/intelligence/price-expectation-v2" element={<PriceExpectationV2Page />} />
              
              {/* ═══════════════════════════════════════════════════════════
                  FRACTAL V2.1 — Single entry point with horizontal tabs
                  ═══════════════════════════════════════════════════════════ */}
              <Route path="/fractal" element={<FractalIntelligencePage />} />
              <Route path="/fractal/btc" element={<FractalIntelligencePage />} />
              <Route path="/fractal/spx" element={<FractalIntelligencePage />} />
              <Route path="/fractal/dxy" element={<FractalIntelligencePage />} />
              <Route path="/fractal/overview" element={<FractalIntelligencePage />} />
              <Route path="/fractal/signal" element={<FractalIntelligencePage />} />
              <Route path="/fractal/matches" element={<FractalIntelligencePage />} />
              <Route path="/brain" element={<FractalIntelligencePage />} />
              <Route path="/intelligence/brain" element={<FractalIntelligencePage />} />
              <Route path="/overview" element={<FractalIntelligencePage />} />
              <Route path="/bitcoin" element={<FractalIntelligencePage />} />
              <Route path="/combined" element={<CombinedTerminalPage />} />
              
              {/* On-chain v3 - New Architecture */}
              <Route path="/intelligence/onchain-v3" element={<OnchainV3Page />} />
              <Route path="/onchain-v3" element={<OnchainV3Page />} />
              
              {/* Phase 2: Wallet Intelligence — always inside On-chain */}
              <Route path="/wallet" element={<Navigate to="/intelligence/onchain-v3?tab=wallet" replace />} />
              <Route path="/wallet/:address" element={<WalletRedirect />} />
              
              {/* Twitter Intelligence — Unified Module (like On-chain) */}
              <Route path="/twitter" element={<TwitterPage />} />
              <Route path="/twitter/overview" element={<TwitterPage />} />

              {/* Connections → Twitter Redirects (SEO + bookmarks + deep-links) */}
              <Route path="/connections" element={<Navigate to="/twitter" replace />} />
              <Route path="/connections/unified" element={<Navigate to="/twitter?tab=influencers" replace />} />
              <Route path="/connections/groups" element={<Navigate to="/twitter?tab=influencers" replace />} />
              <Route path="/connections/radar" element={<Navigate to="/twitter?tab=radar" replace />} />
              <Route path="/connections/reality" element={<Navigate to="/twitter?tab=reality" replace />} />
              <Route path="/connections/graph" element={<Navigate to="/twitter?tab=graph" replace />} />
              <Route path="/connections/graph-v2" element={<Navigate to="/twitter?tab=graph" replace />} />
              <Route path="/connections/clusters" element={<Navigate to="/twitter?tab=clusters" replace />} />
              <Route path="/connections/cluster-attention" element={<Navigate to="/twitter?tab=clusters" replace />} />
              <Route path="/connections/alt-season" element={<Navigate to="/twitter?tab=altseason" replace />} />
              <Route path="/connections/opportunities" element={<Navigate to="/twitter?tab=altseason" replace />} />
              <Route path="/connections/lifecycle" element={<Navigate to="/twitter?tab=lifecycle" replace />} />
              <Route path="/connections/narratives" element={<Navigate to="/twitter?tab=narratives" replace />} />
              <Route path="/connections/alpha" element={<Navigate to="/twitter?tab=narratives" replace />} />
              <Route path="/connections/backers" element={<Navigate to="/twitter?tab=credibility" replace />} />
              <Route path="/connections/backers/:slug" element={<Navigate to="/twitter?tab=credibility" replace />} />
              <Route path="/connections/backers" element={<Navigate to="/twitter?tab=credibility" replace />} />
              <Route path="/connections/backers/:slug" element={<BakerDetailPage />} />
              {/* Legacy redirect */}
              <Route path="/connections/bakery" element={<Navigate to="/connections/backers" replace />} />
              <Route path="/connections/bakery/:slug" element={<Navigate to="/connections/backers/:slug" replace />} />
              <Route path="/connections/influencers" element={<Navigate to="/twitter?tab=influencers" replace />} />
              <Route path="/connections/influencers/:handle" element={<InfluencerDetailPage />} />
              <Route path="/connections/watchlists" element={<Navigate to="/twitter?tab=influencers" replace />} />
              <Route path="/connections/watchlists/:id" element={<ConnectionsWatchlistPage />} />
              <Route path="/connections/farm-network" element={<Navigate to="/twitter?tab=bot-detection" replace />} />
              <Route path="/connections/strategy-simulation" element={<Navigate to="/twitter" replace />} />
              <Route path="/connections/:authorId" element={<ConnectionsDetailPage />} />
              
              {/* Phase 1.2 - Market Product Pages */}
              <Route path="/market/:symbol" element={<MarketAssetPage />} />
              
              {/* P1 - ML Monitoring Dashboard */}
              <Route path="/ml-monitoring" element={<MLMonitoringPage />} />
              
              {/* Advanced v2 - 3 screens */}
              <Route path="/advanced/system-overview" element={<SystemOverview />} />
              <Route path="/advanced/ml-health" element={<MLHealth />} />
              <Route path="/advanced/signals-attribution" element={<SignalsAttribution />} />
              
              {/* B4 - Twitter Parser User UI */}
              <Route path="/dashboard/parser" element={<ParserOverviewPage />} />
              <Route path="/parsing" element={<ParserOverviewPage />} />
              
              {/* P4.1 - Twitter Integration (User-Owned Accounts) */}
              <Route path="/dashboard/twitter" element={<TwitterIntegrationPage />} />
              <Route path="/dashboard/twitter/targets" element={<TwitterTargetsPage />} />
              
              {/* S2.2 - Sentiment Analyzer */}
              <Route path="/sentiment" element={<SentimentPage />} />

              {/* RESTORED 2026-05-16: Tech Analysis = Full 8-tab Workspace (TA | Trading) */}
              <Route path="/tech-analysis" element={<TerminalWorkspacePage />} />
              <Route path="/tech-analysis/:symbol" element={<TerminalWorkspacePage />} />
              <Route path="/tech-analysis/compact" element={<TechAnalysisPage />} />
              <Route path="/terminal" element={<TerminalWorkspacePage />} />
              <Route path="/terminal/cognitive" element={<CognitiveTerminalPage />} />
              {/* /trading → full 8-tab workspace (TA + Trading unified) */}
              <Route path="/trading" element={<TerminalWorkspacePage />} />
              <Route path="/trading/compact" element={<TradingTerminalPage />} />
              <Route path="/trading/portfolio" element={<TradingPortfolioPage />} />
              <Route path="/ideas" element={<Navigate to="/tech-analysis" replace />} />
              
              {/* Prediction Markets — Event Probability Intelligence */}
              <Route path="/prediction-markets" element={<PredictionMarketsPage />} />
              {/* Telegram Intelligence Module (Plugin) */}
              <Route path="/telegram" element={<TelegramEntitiesPage />} />
              <Route path="/telegram/entities" element={<TelegramEntitiesPage />} />
              <Route path="/telegram/feed" element={<TelegramFeedPage />} />
              {/* /telegram/network route removed */}
              <Route path="/telegram/channel/:username" element={<TelegramChannelOverviewPage />} />
              <Route path="/telegram/:username" element={<TelegramChannelOverviewPage />} />
              
              {/* S3.9 - Twitter Feed (Sentiment без цены) */}
              <Route path="/sentiment/twitter" element={<TwitterFeedPage />} />
              
              {/* S5 - Twitter AI (Sentiment × Price) */}
              <Route path="/sentiment/twitter-ai" element={<TwitterAIPage />} />
              
              {/* P4.1 - Settings */}
              <Route path="/settings/notifications" element={<NotificationsSettingsPage />} />
              <Route path="/settings/api-keys" element={<ApiKeysSettingsPage />} />
              
              {/* P1.8 - Graph Intelligence */}
              <Route path="/graph-intelligence" element={<GraphIntelligencePage />} />
              
              {/* Wallet v2 — standalone page (inside AppLayout) */}
              
              {/* Legacy Market Signals route (redirects to Market Hub) */}
              {/* /market-signals now handled above as redirect to MarketHub */}
              
              {/* TOKEN ROUTING - NEW CANONICAL ARCHITECTURE */}
              {/* Canonical URL: /token/:chainId/:address - Source of truth */}
              <Route path="/token/:chainId/:address" element={<TokenCanonicalPage />} />
              {/* Alias URL: /token/:symbol - Resolves to canonical */}
              <Route path="/token/:symbol" element={<TokenAliasResolver />} />
              
              {/* Legacy token routes (backwards compatibility) */}
              {/* DECOMMISSIONED: Legacy token detail → Assets deep dive */}
              <Route path="/tokens/:address" element={<Navigate to="/intelligence/onchain-v3?tab=assets" replace />} />
              
              {/* Other Detail Pages */}
              <Route path="/portfolio/:address" element={<Portfolio />} />
              <Route path="/portfolio" element={<Portfolio />} />
              <Route path="/entity/:entityId" element={<EntityDetail />} />
              <Route path="/signal/:id" element={<SignalSnapshot />} />
              
              {/* Fallback */}
              <Route path="/*" element={<Navigate to="/intelligence/price-expectation-v2" replace />} />
            </Route>
          </Routes>
        </Suspense>
        <Toaster position="top-right" />
        </AuthProvider>
      </BrowserRouter>
      </AdminAuthProvider>
      </ActivePathProvider>
    </WebSocketProvider>
  );
}

export default App;
