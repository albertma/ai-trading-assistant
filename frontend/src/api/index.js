import axios from 'axios'

const api = axios.create({
    baseURL: '/api/v1',
    timeout: 60000,
})

// ========== 市场 ==========
export function getMarketOverview(params = {}) {
    return api.get('/market/overview', { params })
}

export function getMarketDates() {
    return api.get('/market/dates')
}

export function getSectors(date) {
    const params = date ? { date } : {}
    return api.get('/market/sectors', { params })
}

export function getSentimentCycle(days = 7) {
    return api.get('/market/sentiment-cycle', { params: { days } })
}

export function getIndexHistory(days = 60) {
    return api.get('/market/index-history', { params: { days } })
}

// ========== 持仓 ==========
export function getPositions() {
    return api.get('/positions')
}

export function addPosition(data) {
    return api.post('/positions', data)
}

export function updatePosition(code, data) {
    return api.put(`/positions/${code}`, data)
}

export function deletePosition(code) {
    return api.delete(`/positions/${code}`)
}

// ========== 交易日志 ==========
export function getTrades(code) {
    return api.get(`/positions/${code}/trades`)
}
export function addTrade(code, data) {
    return api.post(`/positions/${code}/trades`, data)
}
export function updateTrade(code, tradeId, data) {
    return api.put(`/positions/${code}/trades/${tradeId}`, data)
}
export function deleteTrade(code, tradeId) {
    return api.delete(`/positions/${code}/trades/${tradeId}`)
}
export function getPositionAnalysis() {
    return api.get('/positions/analysis')
}

// ========== 分析 ==========
export function analyzeStock(code) {
    return api.get(`/analysis/${code}`)
}

// ========== 基本面 ==========
export function getFundamental(code) {
    return api.get(`/fundamental/${code}`)
}
export function getDupontAnalysis(code) {
    return api.get(`/fundamental/dupont/${code}`)
}
export function getDupontCommentary(code) {
    return api.get(`/fundamental/dupont/${code}/commentary`)
}
export function getExpenseAnalysis(code) {
    return api.get(`/fundamental/expense/${code}`)
}
export function getFinancialStatements(code) {
    return api.get(`/fundamental/statements/${code}`)
}
export function getComprehensiveAnalysis(code) {
    return api.get(`/fundamental/comprehensive/${code}`)
}
export function getSupplyChain(code) {
    return api.get(`/fundamental/${code}/supply_chain`)
}
export function getContradiction(code) {
    return api.get(`/fundamental/${code}/contradiction`)
}

// ========== 产业链管理 ==========
export function listIndustryChains(params = {}) {
    return api.get('/fundamental/chain-admin', { params })
}
export function getIndustryStocks(industry, board = '') {
    return api.get(`/fundamental/chain-admin/${encodeURIComponent(industry)}/stocks`, {
        params: board ? { board } : {}
    })
}
export function getIndustryChain(industry) {
    return api.get(`/fundamental/chain-admin/${encodeURIComponent(industry)}`)
}
export function saveIndustryChain(industry, chainData, notes = '') {
    return api.post(`/fundamental/chain-admin/${encodeURIComponent(industry)}`, { chain_data: chainData, notes })
}
export function deleteIndustryChain(industry) {
    return api.delete(`/fundamental/chain-admin/${encodeURIComponent(industry)}`)
}
export function listConceptBoards() {
    return api.get('/fundamental/chain-admin/concept-boards')
}
export function listUnmappedIndustries() {
    return api.get('/fundamental/chain-admin/industries/unmapped')
}
export function extractChainFromArticle(data) {
    return api.post('/fundamental/chain-admin/extract', data)
}
export function saveExtractedChain(data) {
    return api.post('/fundamental/chain-admin/extract/save', data)
}

// ========== 档案 ==========
export function getStockProfile(code) {
    return api.get(`/profile/${code}`)
}
export function getAnalysisHistory() {
    return api.get('/profile')
}
export function getAllAnalysisHistory(limit = 100) {
    return api.get('/profile/all-history', { params: { limit } })
}
export function addStockNote(code, note) {
    return api.post(`/profile/${code}/note`, { note })
}

export function saveSnapshot(code, data) {
    return api.post(`/profile/${code}/save-snapshot`, data)
}

export function updateDraftNotes(code, notes) {
    return api.put(`/profile/${code}/draft-notes`, { notes })
}

export function listSnapshots(code) {
    return api.get(`/profile/${code}/snapshots`)
}

export function deleteSnapshot(code, snapshotId) {
    return api.delete(`/profile/${code}/snapshot/${snapshotId}`)
}

export function deleteDraft(code, analysisDate) {
    return api.delete(`/profile/${code}/draft/${analysisDate}`)
}

export function saveFullAnalysis(code, data) {
    return api.post(`/profile/${code}/save-full-analysis`, data)
}

// ========== 风控 ==========
export function getRiskAlerts() {
    return api.get('/risk/alerts')
}

// ========== 报告 ==========
export function getDailyReport() {
    return api.get('/reports/daily')
}

export function getReportByDate(date) {
    return api.get(`/reports/${date}`)
}

export function getReportList() {
    return api.get('/reports/list')
}

export default api


// ========== 观察池 ==========
export function getWatchlist() {
    return api.get('/watchlist')
}
export function addWatchItem(data) {
    return api.post('/watchlist', data)
}
export function removeWatchItem(code) {
    return api.delete(`/watchlist/${code}`)
}
export function updateWatchItem(code, priority, notes = null) {
    const params = { priority }
    if (notes !== null) params.notes = notes
    return api.put(`/watchlist/${code}`, null, { params })
}
export function getWatchChart(code, days = 30) {
    return api.get(`/watchlist/${code}/chart`, { params: { days } })
}
export function getWatchFundamental(code) {
    return api.get(`/watchlist/${code}/fundamental`)
}
export function refreshWatchKline(code) {
    return api.post(`/watchlist/refresh-kline/${code}`)
}
export function refreshAllKline() {
    return api.post('/watchlist/refresh-kline')
}
export function getLocalKline(code, days = 400) {
    return api.get(`/watchlist/local-kline/${code}`, { params: { days } })
}

// ========== AI聊天 ==========
export function chatWithAI(code, message, history = []) {
    return api.post(`/chat/${code}`, { message, history })
}
export function getChatHistory(code, limit = 50) {
    return api.get(`/chat/${code}/history`, { params: { limit } })
}
export function clearChatHistory(code) {
    return api.delete(`/chat/${code}/history`)
}
export function summarizeChat(code) {
    return api.post(`/chat/${code}/summarize`)
}
export function getAiAnalyses(code, limit = 5) {
    return api.get(`/chat/${code}/analyses`, { params: { limit } })
}
export function clearAiAnalyses(code) {
    return api.delete(`/chat/${code}/analyses`)
}

// ========== 个股资料 ==========
export function searchStockInfo(q, limit = 15) {
    return api.get('/stock-info/search', { params: { q, limit } })
}
export function getStockInfoDetail(code) {
    return api.get(`/stock-info/${code}`)
}
export function refreshStockInfo() {
    return api.post('/stock-info/refresh')
}
export function refreshStockInfoDetail(code) {
    return api.post(`/stock-info/refresh-detail/${code}`)
}
export function getStockInfoCount() {
    return api.get('/stock-info/count')
}

// ========== 风控规则 ==========
export function getRiskRules() {
    return api.get('/risk-rules')
}
export function createRiskRule(data) {
    return api.post('/risk-rules', data)
}
export function updateRiskRule(id, data) {
    return api.put(`/risk-rules/${id}`, data)
}
export function deleteRiskRule(id) {
    return api.delete(`/risk-rules/${id}`)
}
export function toggleRiskRule(id) {
    return api.patch(`/risk-rules/${id}/toggle`)
}
export function getRiskRuleTypes() {
    return api.get('/risk-rules/types')
}
export function initDefaultRiskRules() {
    return api.post('/risk-rules/init-defaults')
}
