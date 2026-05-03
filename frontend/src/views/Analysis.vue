<template>
    <div class="analysis-page">
        <el-card shadow="hover" style="margin-bottom: 16px;">
            <el-row :gutter="12">
                <el-col :span="6">
                    <el-autocomplete v-model="stockCode"
                        :fetch-suggestions="querySearch"
                        @select="handleSelect"
                        placeholder="输入代码/名称/拼音（如 600519、贵州茅台、zgmt）"
                        size="large" clearable :trigger-on-focus="false"
                        @keyup.enter="search">
                        <template #prefix>
                            <el-icon><Search /></el-icon>
                        </template>
                        <template #default="{ item }">
                            <div style="display:flex;justify-content:space-between;align-items:center;">
                                <span><b>{{ item.code }}</b> {{ item.name }}</span>
                                <el-tag size="small" type="info" effect="plain">{{ item.market }}</el-tag>
                            </div>
                        </template>
                    </el-autocomplete>
                </el-col>
                <el-col :span="3">
                    <el-button type="primary" size="large" @click="search" :loading="loading">
                        {{ loading ? '分析中...' : '深度分析' }}
                    </el-button>
                </el-col>
            </el-row>
        </el-card>

        <!-- 风控栏目：基于数据库规则，只显示未通过 -->
        <el-card v-if="result && result.custom_risk" shadow="hover"
            style="margin-bottom:16px;"
            :style="{ borderLeft: `4px solid ${allFailedRules.length === 0 ? '#67c23a' : '#f56c6c'}` }">
            <template #header>
                <div style="display:flex;align-items:center;justify-content:space-between;">
                    <div style="display:flex;align-items:center;gap:8px;">
                        <el-tag :type="allFailedRules.length === 0 ? 'success' : 'danger'" size="large" effect="dark">
                            {{ allFailedRules.length === 0 ? '✅ 风控通过' : `❌ ${allFailedRules.length} 项未通过` }}
                        </el-tag>
                        <b>{{ result.name }} ({{ result.code }})</b>
                        <span v-if="result.technical" style="color:#909399;font-size:13px;">
                            现价 {{ result.technical.current_price?.toFixed(2) }}
                        </span>
                    </div>
                    <div style="display:flex;align-items:center;gap:8px;">
                        <el-button v-if="!inWatchlist" size="small" type="warning" plain
                            :loading="watchlistLoading" @click="addToWatchlist">
                            + 观察池
                        </el-button>
                        <el-tag v-else size="small" type="success" effect="plain">
                            ✓ 已在观察池
                        </el-tag>
                        <el-button size="small" text type="primary" @click="$router.push('/risk-rules')">
                            规则管理 &raquo;
                        </el-button>
                    </div>
                </div>
            </template>
            <div v-if="allFailedRules.length === 0" style="text-align:center;padding:12px;color:#67c23a;">
                ✅ 所有风控规则全部通过
            </div>
            <el-row :gutter="12">
                <el-col :span="8" v-for="check in allFailedRules" :key="check.rule">
                    <el-card shadow="never" :class="'risk-' + check.status">
                        <div class="risk-title">{{ check.rule }}</div>
                        <div class="risk-value">{{ check.detail }}</div>
                        <div class="risk-status">
                            <el-tag :type="check.status === 'fail' ? 'danger' : 'warning'" size="small">
                                {{ check.status === 'fail' ? '禁止买入' : '谨慎关注' }}
                            </el-tag>
                        </div>
                    </el-card>
                </el-col>
            </el-row>
        </el-card>

        <!-- 选项卡面板 -->
        <el-tabs v-if="result" v-model="activeTab" type="border-card" @tab-click="onTabClick">
            <!-- Tab 1: 技术面 -->
            <el-tab-pane label="📈 技术面" name="tech">
                <el-row :gutter="16" v-if="result.technical">
                    <el-col :span="12">
                        <el-card shadow="hover">
                            <template #header><b>均线与指标</b></template>
                            <el-descriptions :column="2" border size="small">
                                <el-descriptions-item label="现价">{{ t.tech.current_price?.toFixed(2) }}</el-descriptions-item>
                                <el-descriptions-item label="涨幅">
                                    <span :style="{ color: (t.tech.change_pct||0) >= 0 ? '#f56c6c' : '#67c23a' }">
                                        {{ (t.tech.change_pct||0).toFixed(2) }}%
                                    </span>
                                </el-descriptions-item>
                                <el-descriptions-item label="MA5">{{ t.tech.ma5?.toFixed(2) || '--' }}</el-descriptions-item>
                                <el-descriptions-item label="MA10">{{ t.tech.ma10?.toFixed(2) || '--' }}</el-descriptions-item>
                                <el-descriptions-item label="MA20">{{ t.tech.ma20?.toFixed(2) || '--' }}</el-descriptions-item>
                                <el-descriptions-item label="MA60">{{ t.tech.ma60?.toFixed(2) || '--' }}</el-descriptions-item>
                                <el-descriptions-item label="MA200">{{ t.tech.ma200?.toFixed(2) || '--' }}</el-descriptions-item>
                                <el-descriptions-item label="均线多头">
                                    <el-tag :type="t.tech.bullish_alignment ? 'success' : 'info'" size="small">
                                        {{ t.tech.bullish_alignment ? '是' : '否' }}
                                    </el-tag>
                                </el-descriptions-item>
                                <el-descriptions-item label="MACD(DIF)">{{ t.tech.macd?.dif || '--' }}</el-descriptions-item>
                                <el-descriptions-item label="MACD(DEA)">{{ t.tech.macd?.dea || '--' }}</el-descriptions-item>
                                <el-descriptions-item label="MACD(柱)">{{ t.tech.macd?.hist || '--' }}</el-descriptions-item>
                                <el-descriptions-item label="RSI(14)">{{ t.tech.rsi_14 || '--' }}</el-descriptions-item>
                            </el-descriptions>
                        </el-card>
                    </el-col>
                    <el-col :span="12">
                        <el-card shadow="hover">
                            <template #header><b>📰 相关新闻</b></template>
                            <div v-if="!result.news?.length" style="color:#909399;text-align:center;padding:20px;">暂无新闻</div>
                            <div v-for="(n, i) in (result.news || [])" :key="i" class="news-item">
                                <div class="news-title">
                                    <a :href="n.url" target="_blank" rel="noopener" v-if="n.url">{{ n.title }}</a>
                                    <span v-else>{{ n.title }}</span>
                                </div>
                                <div class="news-time">{{ n.time }} <span v-if="n.source">· {{ n.source }}</span></div>
                            </div>
                        </el-card>
                    </el-col>
                </el-row>
                <el-empty v-else description="暂无技术面数据" />
            </el-tab-pane>

            <!-- Tab 2: K线形态 + K线图 -->
            <el-tab-pane label="🕯️ K线图表" name="kline">
                <!-- K线图容器 -->
                <div ref="klineChartRef" style="width:100%;height:520px;margin-bottom:16px;"></div>
                <div v-if="klineLoading" style="text-align:center;padding:30px;color:#909399;">
                    <el-icon class="is-loading" :size="24"><Loading /></el-icon>
                    <p style="margin-top:8px;">加载K线数据...</p>
                </div>
                <!-- 形态描述卡片 -->
                <el-divider content-position="left">📋 K线形态识别</el-divider>
                <div v-if="result.technical?.kline_patterns?.length">
                    <el-row :gutter="12">
                        <el-col :span="8" v-for="(p, i) in result.technical.kline_patterns" :key="i" style="margin-bottom:12px;">
                            <el-card shadow="hover" :class="'pattern-' + p.direction">
                                <div class="pattern-header">
                                    <span class="pattern-name">{{ p.pattern }}</span>
                                    <el-tag :type="p.direction === 'bullish' ? 'danger' : p.direction === 'bearish' ? 'success' : 'info'" size="small" effect="dark">
                                        {{ p.direction === 'bullish' ? '📈 看涨' : p.direction === 'bearish' ? '📉 看跌' : '➡️ 中性' }}
                                    </el-tag>
                                    <el-tag :type="p.confidence === 'high' ? 'warning' : p.confidence === 'medium' ? 'primary' : 'info'" size="small" style="margin-left:4px;">
                                        {{ p.confidence === 'high' ? '高置信' : p.confidence === 'medium' ? '中置信' : '低置信' }}
                                    </el-tag>
                                </div>
                                <div class="pattern-desc">{{ p.description }}</div>
                            </el-card>
                        </el-col>
                    </el-row>
                </div>
                <el-empty v-else-if="result.technical" description="未识别出明显K线形态" />
                <el-empty v-else description="暂无技术面数据" />
            </el-tab-pane>

            <!-- Tab 3: 基本面 -->
            <el-tab-pane label="📊 基本面" name="fundamental">
                <div v-if="fundLoading" style="text-align:center;padding:40px;"><el-icon class="is-loading" :size="32"><Loading /></el-icon></div>
                <template v-else-if="fundData">
                    <el-card shadow="hover" style="margin-bottom:16px;">
                        <template #header><b>📋 财务摘要（最近5期）</b></template>
                        <el-table :data="fundData.financial_summary?.records || []" border size="small" style="width:100%"
                            :default-sort="{ prop: '报告期', order: 'descending' }">
                            <el-table-column prop="报告期" label="报告期" width="110" sortable />
                            <el-table-column prop="营业总收入" label="营收(亿)" width="90">
                                <template #default="{ row }">{{ row?.['营业总收入'] ?? '--' }}</template>
                            </el-table-column>
                            <el-table-column prop="营业总收入同比增长率" label="营收同比" width="80">
                                <template #default="{ row }">
                                    <span :style="{ color: (Number(row?.['营业总收入同比增长率'])||0) >= 0 ? '#f56c6c' : '#67c23a' }">{{ row?.['营业总收入同比增长率'] ? row?.['营业总收入同比增长率']+'%' : '--' }}</span>
                                </template>
                            </el-table-column>
                            <el-table-column prop="净利润" label="净利(亿)" width="85">
                                <template #default="{ row }">{{ row?.['净利润'] ?? '--' }}</template>
                            </el-table-column>
                            <el-table-column prop="净利润同比增长率" label="净利同比" width="80">
                                <template #default="{ row }">
                                    <span :style="{ color: (Number(row['净利润同比增长率'])||0) >= 0 ? '#f56c6c' : '#67c23a' }">{{ row['净利润同比增长率'] ? row['净利润同比增长率']+'%' : '--' }}</span>
                                </template>
                            </el-table-column>
                            <el-table-column prop="销售毛利率" label="毛利率" width="70">
                                <template #default="{ row }">{{ row?.['销售毛利率'] ?? '--' }}%</template>
                            </el-table-column>
                            <el-table-column prop="销售净利率" label="净利率" width="70">
                                <template #default="{ row }">{{ row?.['销售净利率'] ?? '--' }}%</template>
                            </el-table-column>
                            <el-table-column prop="净资产收益率" label="ROE" width="70">
                                <template #default="{ row }">{{ row?.['净资产收益率'] ?? '--' }}%</template>
                            </el-table-column>
                            <el-table-column prop="基本每股收益" label="EPS" width="70" />
                            <el-table-column prop="每股净资产" label="BPS" width="70" />
                            <el-table-column prop="资产负债率" label="负债率" width="70">
                                <template #default="{ row }">{{ row?.['资产负债率'] ?? '--' }}%</template>
                            </el-table-column>
                            <el-table-column prop="流动比率" label="流动比" width="65" />
                        </el-table>
                    </el-card>
                    <el-card v-if="fundData.revenue_breakdown?.length" shadow="hover" style="margin-bottom:16px;">
                        <template #header><b>🏭 主营业务</b></template>
                        <div v-for="(item, i) in fundData.revenue_breakdown" :key="i" class="biz-item">
                            <div class="biz-field" v-if="item.business"><label>主营业务：</label>{{ item.business }}</div>
                            <div class="biz-field" v-if="item.product_type"><label>产品类型：</label>{{ item.product_type }}</div>
                            <div class="biz-field" v-if="item.products"><label>产品名称：</label>{{ item.products }}</div>
                            <div class="biz-field" v-if="item.scope"><label>经营范围：</label>{{ item.scope }}</div>
                            <el-divider v-if="i < fundData.revenue_breakdown.length - 1" />
                        </div>
                    </el-card>
                    <!-- 详细财报（内嵌） -->
                    <template v-if="statementsData">
                        <!-- 三张报表 -->
                        <el-card shadow="hover" style="margin-bottom:16px;">
                            <template #header>
                                <b>📄 三张财务报表</b>
                                <el-button size="small" type="primary" plain style="float:right;" @click="statementsVisible = true">全屏查看</el-button>
                            </template>
                            <el-tabs type="border-card">
                                <el-tab-pane label="📊 利润表">
                                    <el-table :data="statementsData.profit_sheet || []" border size="small" style="width:100%"
                                        :default-sort="{ prop: 'period', order: 'descending' }" max-height="350">
                                        <el-table-column prop="period" label="报告期" width="110" sortable fixed />
                                        <el-table-column v-for="col in getStatementFields('profit_sheet')" :key="col" :label="col" width="120">
                                            <template #default="{ row }">{{ formatVal(row.items?.[col]) }}</template>
                                        </el-table-column>
                                    </el-table>
                                </el-tab-pane>
                                <el-tab-pane label="🏛️ 资产负债表">
                                    <el-table :data="statementsData.balance_sheet || []" border size="small" style="width:100%"
                                        :default-sort="{ prop: 'period', order: 'descending' }" max-height="350">
                                        <el-table-column prop="period" label="报告期" width="110" sortable fixed />
                                        <el-table-column v-for="col in getStatementFields('balance_sheet')" :key="col" :label="col" width="120">
                                            <template #default="{ row }">{{ formatVal(row.items?.[col]) }}</template>
                                        </el-table-column>
                                    </el-table>
                                </el-tab-pane>
                                <el-tab-pane label="💵 现金流量表">
                                    <el-table :data="statementsData.cash_flow || []" border size="small" style="width:100%"
                                        :default-sort="{ prop: 'period', order: 'descending' }" max-height="350">
                                        <el-table-column prop="period" label="报告期" width="110" sortable fixed />
                                        <el-table-column v-for="col in getStatementFields('cash_flow')" :key="col" :label="col" width="140">
                                            <template #default="{ row }">{{ formatVal(row.items?.[col]) }}</template>
                                        </el-table-column>
                                    </el-table>
                                </el-tab-pane>
                            </el-tabs>
                        </el-card>
                    </template>
                </template>
                <el-empty v-else-if="!fundLoading" description="暂无基本面数据" />
                <div v-else style="text-align:center;padding:40px;color:#909399;">加载中...</div>
            </el-tab-pane>

            <!-- Tab 3c: 综合评估（6大维度+同行对比+管理层） -->
            <el-tab-pane label="🎯 综合评估" name="comprehensive">
                <div v-if="comprehensiveLoading" style="text-align:center;padding:40px;">
                    <el-icon class="is-loading" :size="32"><Loading /></el-icon>
                    <p style="color:#909399;margin-top:8px;">加载综合评估...</p>
                </div>
                <template v-else-if="comprehensiveData">
                    <!-- 总分 -->
                    <el-card shadow="hover" style="margin-bottom:16px;border:1px solid #334;"
                        :style="{ background: comprehensiveData.total_pct >= 65 ? 'linear-gradient(135deg, #1a2e1a, #1a1a2e)' : comprehensiveData.total_pct >= 45 ? 'linear-gradient(135deg, #2e2a1a, #1a1a2e)' : 'linear-gradient(135deg, #2e1a1a, #1a1a2e)' }">
                        <div style="display:flex;align-items:center;justify-content:space-between;">
                            <div style="display:flex;align-items:center;gap:12px;">
                                <span style="font-size:32px;">{{ comprehensiveData.total_pct >= 65 ? '🟢' : comprehensiveData.total_pct >= 45 ? '🟠' : '🔴' }}</span>
                                <div>
                                    <span style="font-size:20px;font-weight:bold;color:#e0e0e0;">综合基本面评分</span>
                                    <span style="font-size:28px;font-weight:bold;margin-left:12px;color:#409eff;">{{ comprehensiveData.total_score }}</span>
                                    <span style="color:#909399;font-size:14px;">/ {{ comprehensiveData.total_max }}</span>
                                </div>
                                <el-tag v-if="comprehensiveData.industry" type="info" size="small" style="margin-left:8px;">{{ comprehensiveData.industry }}</el-tag>
                            </div>
                            <div style="font-size:28px;font-weight:bold;color:#e0e0e0;">{{ comprehensiveData.total_pct }}%</div>
                        </div>
                    </el-card>

                    <!-- 6大维度卡片 -->
                    <el-row :gutter="12" style="margin-bottom:16px;">
                        <el-col :span="8" v-for="dim in comprehensiveData.dimensions" :key="dim.key" style="margin-bottom:12px;">
                            <el-card shadow="hover" style="height:100%;border:1px solid #2a2a3e;">
                                <div style="display:flex;justify-content:space-between;align-items:center;margin-bottom:8px;">
                                    <span style="font-size:14px;font-weight:bold;color:#ccc;">{{ dim.icon }} {{ dim.name }}</span>
                                    <span :style="{ color: dim.score >= dim.max*0.65 ? '#67c23a' : dim.score >= dim.max*0.45 ? '#e6a23c' : '#f56c6c', fontWeight:'bold', fontSize:'16px' }">
                                        {{ dim.score }}/{{ dim.max }}
                                    </span>
                                </div>
                                <div style="height:5px;background:rgba(255,255,255,0.08);border-radius:3px;overflow:hidden;margin-bottom:10px;">
                                    <div :style="{ width: (dim.score/dim.max*100)+'%', height:'5px', background: dim.score >= dim.max*0.65 ? '#67c23a' : dim.score >= dim.max*0.45 ? '#e6a23c' : '#f56c6c', borderRadius:'3px' }"></div>
                                </div>
                                <div v-for="(item, ii) in dim.items" :key="ii" style="display:flex;justify-content:space-between;align-items:center;padding:3px 0;font-size:12px;border-bottom:1px solid rgba(255,255,255,0.04);">
                                    <span style="color:#909399;">{{ item.label }}</span>
                                    <div>
                                        <span style="color:#e0e0e0;font-weight:bold;margin-right:6px;">{{ item.value }}</span>
                                        <el-tag :type="item.score >= item.max*0.65 ? 'success' : item.score >= item.max*0.45 ? 'warning' : 'danger'" size="small" style="font-size:10px;">
                                            {{ item.verdict }}
                                        </el-tag>
                                    </div>
                                </div>
                            </el-card>
                        </el-col>
                    </el-row>

                    <!-- 同行对比 -->
                    <el-card v-if="comprehensiveData.peer_comparison?.comparisons?.length" shadow="hover" style="margin-bottom:16px;">
                        <template #header>
                            <b>🤝 同行对比</b>
                            <span style="float:right;font-size:12px;color:#909399;">
                                报告期: {{ comprehensiveData.peer_comparison.raw_report?.报告期 || '--' }}
                            </span>
                        </template>
                        <!-- 原始报表数据验证 -->
                        <el-collapse style="margin-bottom:12px;">
                            <el-collapse-item title="📋 原始报表数据（亿元）" name="raw">
                                <el-table :data="rawReportRows(comprehensiveData.peer_comparison.raw_report)" border size="small" style="width:100%" max-height="300">
                                    <el-table-column prop="item" label="项目" width="100" />
                                    <el-table-column prop="value" label="数值(亿)" width="100">
                                        <template #default="{ row }">
                                            <span v-if="row.value != null">{{ row.value }}</span>
                                            <span v-else style="color:#909399;">--</span>
                                        </template>
                                    </el-table-column>
                                    <el-table-column prop="source" label="来源" width="80" />
                                    <el-table-column prop="desc" label="说明" min-width="200" />
                                </el-table>
                            </el-collapse-item>
                        </el-collapse>
                        <el-table :data="comprehensiveData.peer_comparison.comparisons" border size="small" style="width:100%">
                            <el-table-column label="指标" width="100">
                                <template #default="{ row }">{{ row.label }}</template>
                            </el-table-column>
                            <el-table-column label="类别" width="70">
                                <template #default="{ row }">
                                    <el-tag size="small" :type="row.category === 'profitability' ? 'success' : row.category === 'growth' ? 'warning' : row.category === 'cashflow' ? 'info' : row.category === 'operations' ? 'primary' : 'danger'">
                                        {{ {growth:'成长',profitability:'盈利',cashflow:'现金',operations:'运营',solvency:'偿债'}[row.category] || row.category }}
                                    </el-tag>
                                </template>
                            </el-table-column>
                            <el-table-column label="本股" width="70">
                                <template #default="{ row }">{{ row.company }}{{ row.unit }}</template>
                            </el-table-column>
                            <el-table-column label="行业均值" width="80">
                                <template #default="{ row }">{{ row.peer_avg }}{{ row.unit }}</template>
                            </el-table-column>
                            <el-table-column label="差值" width="80">
                                <template #default="{ row }">
                                    <span :style="{ color: row.better ? '#67c23a' : '#f56c6c' }">{{ row.diff > 0 ? '+': '' }}{{ row.diff }}{{ row.unit }}</span>
                                </template>
                            </el-table-column>
                            <el-table-column label="结论" width="90">
                                <template #default="{ row }">
                                    <el-tag :type="row.better ? 'success' : 'danger'" size="small">{{ row.verdict }}</el-tag>
                                </template>
                            </el-table-column>
                            <el-table-column label="计算公式（原始数据验证）" min-width="300">
                                <template #default="{ row }">
                                    <span v-if="row.raw_calc" style="font-size:11px;color:#909399;font-family:monospace;">{{ row.raw_calc }}</span>
                                    <span v-else style="color:#909399;font-size:11px;">--</span>
                                </template>
                            </el-table-column>
                        </el-table>
                    </el-card>

                    <!-- 管理层分析 -->
                    <el-card v-if="comprehensiveData.management" shadow="hover" style="margin-bottom:16px;">
                        <template #header><b>👔 管理层分析</b></template>
                        <el-row :gutter="16">
                            <el-col :span="12">
                                <el-card shadow="never" style="background:rgba(255,255,255,0.03);">
                                    <template #header><b style="font-size:13px;">🏢 主要股东（前10）</b></template>
                                    <div v-for="(h, hi) in (comprehensiveData.management.top_holders || [])" :key="hi" style="display:flex;justify-content:space-between;padding:4px 0;font-size:12px;border-bottom:1px solid rgba(255,255,255,0.04);">
                                        <span style="color:#909399;">{{ h.name }}</span>
                                        <span style="color:#e0e0e0;font-weight:bold;">{{ h.ratio ? h.ratio + '%' : '--' }}</span>
                                    </div>
                                    <div v-if="comprehensiveData.management.total_holders" style="margin-top:8px;font-size:12px;color:#909399;">
                                        股东总数: {{ comprehensiveData.management.total_holders.toLocaleString() }} 户
                                    </div>
                                </el-card>
                            </el-col>
                            <el-col :span="12">
                                <el-card shadow="never" style="background:rgba(255,255,255,0.03);">
                                    <template #header>
                                        <b style="font-size:13px;">📋 高管持股变动</b>
                                        <el-tag v-if="comprehensiveData.management.buy_total" size="small" type="success" style="margin-left:6px;">
                                            共增持{{ comprehensiveData.management.buy_total }}万股
                                        </el-tag>
                                        <el-tag v-if="comprehensiveData.management.sell_total" size="small" type="danger" style="margin-left:4px;">
                                            共减持{{ comprehensiveData.management.sell_total }}万股
                                        </el-tag>
                                    </template>
                                    <div v-if="comprehensiveData.management.changes?.length">
                                        <div v-for="(chg, ci) in comprehensiveData.management.changes.slice(0, 6)" :key="ci" style="display:flex;justify-content:space-between;padding:3px 0;font-size:11px;border-bottom:1px solid rgba(255,255,255,0.04);">
                                            <span style="color:#909399;">{{ chg.date }} {{ chg.person }}</span>
                                            <span>
                                                <el-tag :type="chg.action.includes('增持') ? 'success' : 'danger'" size="small" style="font-size:10px;">{{ chg.action }}</el-tag>
                                                <span style="color:#e0e0e0;margin-left:4px;">¥{{ chg.price }}</span>
                                            </span>
                                        </div>
                                    </div>
                                    <div v-else style="font-size:12px;color:#909399;padding:12px 0;">
                                        {{ comprehensiveData.management.error || '暂无近期高管持股变动' }}
                                    </div>
                                </el-card>
                            </el-col>
                        </el-row>
                    </el-card>

                    <!-- 费用率分析 -->
                    <el-card v-if="comprehensiveData.expense_analysis?.rows?.length" shadow="hover" style="margin-bottom:16px;">
                        <template #header>
                            <b>💰 费用率分析</b>
                            <span style="font-size:12px;color:#909399;margin-left:8px;">
                                <el-tag v-for="(note, ni) in (comprehensiveData.expense_analysis.summary||[])" :key="ni" size="small" :type="note.includes('下降')?'success':'warning'" style="margin-left:4px;">{{ note }}</el-tag>
                            </span>
                        </template>
                        <el-table :data="comprehensiveData.expense_analysis.rows" border size="small" style="width:100%"
                            :default-sort="{ prop: 'period', order: 'descending' }">
                            <el-table-column prop="period" label="报告期" width="110" sortable />
                            <el-table-column prop="revenue" label="营收(亿)" width="85">
                                <template #default="{ row }">{{ row.revenue?.toFixed(1) }}</template>
                            </el-table-column>
                            <el-table-column label="销售费用率" width="85">
                                <template #default="{ row }">
                                    <span v-if="row.sale_ratio != null">{{ row.sale_ratio }}%</span>
                                    <span v-else style="color:#c0c4cc;">--</span>
                                </template>
                            </el-table-column>
                            <el-table-column label="管理费用率" width="85">
                                <template #default="{ row }">
                                    <span v-if="row.manage_ratio != null">{{ row.manage_ratio }}%</span>
                                    <span v-else style="color:#c0c4cc;">--</span>
                                </template>
                            </el-table-column>
                            <el-table-column label="研发费用率" width="85">
                                <template #default="{ row }">
                                    <span v-if="row.research_ratio != null">{{ row.research_ratio }}%</span>
                                    <span v-else style="color:#c0c4cc;">--</span>
                                </template>
                            </el-table-column>
                            <el-table-column label="财务费用率" width="85">
                                <template #default="{ row }">
                                    <span v-if="row.finance_ratio != null" :style="{ color: (row.finance_ratio||0) > 1 ? '#e6a23c' : '#909399' }">{{ row.finance_ratio }}%</span>
                                    <span v-else style="color:#c0c4cc;">--</span>
                                </template>
                            </el-table-column>
                            <el-table-column label="总成本率" width="80">
                                <template #default="{ row }">
                                    <span v-if="row.total_cost_ratio != null">{{ row.total_cost_ratio }}%</span>
                                    <span v-else style="color:#c0c4cc;">--</span>
                                </template>
                            </el-table-column>
                            <el-table-column label="费用yoy" width="120">
                                <template #default="{ row }">
                                    <span v-if="row.manage_yoy != null" :style="{ color: (row.manage_yoy||0) > 0 ? '#f56c6c' : '#67c23a', fontSize:'12px' }">
                                        管理{{ row.manage_yoy > 0 ? '+' : '' }}{{ row.manage_yoy }}%
                                    </span>
                                    <span v-if="row.sale_yoy != null" :style="{ color: (row.sale_yoy||0) > 0 ? '#f56c6c' : '#67c23a', fontSize:'12px', marginLeft:'4px' }">
                                        销售{{ row.sale_yoy > 0 ? '+' : '' }}{{ row.sale_yoy }}%
                                    </span>
                                </template>
                            </el-table-column>
                        </el-table>
                    </el-card>
                </template>
                <el-empty v-else-if="!comprehensiveLoading" description="暂无综合评估数据" />
            </el-tab-pane>

            <!-- Tab 3b: 杜邦分析 -->
            <el-tab-pane label="📐 杜邦分析" name="dupont">
                <div v-if="dupontLoading" style="text-align:center;padding:40px;"><el-icon class="is-loading" :size="32"><Loading /></el-icon></div>
                <template v-else-if="dupontData?.dupont?.rows?.length">
                    <el-row :gutter="16" style="margin-bottom:16px;">
                        <el-col :span="8">
                            <el-card shadow="hover" class="dupont-factor-card">
                                <div class="dupont-factor-title">净利率</div>
                                <div class="dupont-factor-value">{{ latestRow?.net_margin_pct ?? '--' }}%</div>
                                <div class="dupont-factor-desc">盈利能力 · 每元营收赚多少</div>
                            </el-card>
                        </el-col>
                        <el-col :span="8">
                            <el-card shadow="hover" class="dupont-factor-card">
                                <div class="dupont-factor-title">资产周转率</div>
                                <div class="dupont-factor-value">{{ latestRow?.asset_turnover ?? '--' }}x</div>
                                <div class="dupont-factor-desc">运营效率 · 每元资产产生多少营收</div>
                            </el-card>
                        </el-col>
                        <el-col :span="8">
                            <el-card shadow="hover" class="dupont-factor-card">
                                <div class="dupont-factor-title">权益乘数</div>
                                <div class="dupont-factor-value">{{ latestRow?.equity_multiplier ?? '--' }}x</div>
                                <div class="dupont-factor-desc">财务杠杆 · 每元股东权益撬动多少资产</div>
                            </el-card>
                        </el-col>
                    </el-row>
                    <el-card shadow="hover" style="margin-bottom:16px;text-align:center;">
                        <div style="font-size:18px;font-weight:bold;color:#e6a23c;padding:16px;">
                            ROE = {{ latestRow?.net_margin_pct ?? '?' }}% × {{ latestRow?.asset_turnover ?? '?' }} × {{ latestRow?.equity_multiplier ?? '?' }}
                            <span v-if="latestRow?.roe_pct != null" style="margin-left:12px;color:#409eff;">= {{ latestRow.roe_pct }}%</span>
                        </div>
                    </el-card>
                    <el-card shadow="hover" style="margin-bottom:16px;">
                        <template #header><b>📈 杜邦分解趋势（最近5期）</b></template>
                        <el-table :data="dupontData.dupont.rows" border size="small" style="width:100%"
                            :default-sort="{ prop: 'period', order: 'descending' }">
                            <el-table-column prop="period" label="报告期" width="110" sortable />
                            <el-table-column prop="roe_pct" label="ROE(%)" width="80" sortable>
                                <template #default="{ row }">
                                    <span :style="{ color: (row.roe_pct||0) >= 0 ? '#f56c6c' : '#67c23a', fontWeight:'bold' }">{{ row.roe_pct?.toFixed(2) ?? '--' }}%</span>
                                </template>
                            </el-table-column>
                            <el-table-column prop="net_margin_pct" label="净利率(%)" width="80">
                                <template #default="{ row }">
                                    <span :style="{ color: (row.net_margin_pct||0) >= 0 ? '#f56c6c' : '#67c23a' }">{{ row.net_margin_pct?.toFixed(2) ?? '--' }}%</span>
                                </template>
                            </el-table-column>
                            <el-table-column prop="asset_turnover" label="周转率" width="80">
                                <template #default="{ row }">{{ row.asset_turnover?.toFixed(4) ?? '--' }}</template>
                            </el-table-column>
                            <el-table-column prop="equity_multiplier" label="权益乘数" width="90">
                                <template #default="{ row }">{{ row.equity_multiplier?.toFixed(4) ?? '--' }}</template>
                            </el-table-column>
                            <el-table-column prop="revenue" label="营收(亿)" width="90">
                                <template #default="{ row }">{{ row.revenue?.toFixed(1) ?? '--' }}</template>
                            </el-table-column>
                            <el-table-column prop="net_profit" label="净利(亿)" width="85">
                                <template #default="{ row }">{{ row.net_profit?.toFixed(1) ?? '--' }}</template>
                            </el-table-column>
                            <el-table-column prop="total_assets" label="总资产(亿)" width="95">
                                <template #default="{ row }">{{ row.total_assets?.toFixed(1) ?? '--' }}</template>
                            </el-table-column>
                            <el-table-column prop="debt_ratio_pct" label="负债率(%)" width="80">
                                <template #default="{ row }">{{ row.debt_ratio_pct?.toFixed(1) ?? '--' }}%</template>
                            </el-table-column>
                        </el-table>
                    </el-card>
                    <el-card v-if="dupontData.dupont.changes?.length" shadow="hover">
                        <template #header><b>🔄 ROE变化分析</b></template>
                        <el-timeline>
                            <el-timeline-item v-for="(chg, i) in dupontData.dupont.changes" :key="i"
                                :type="chg.direction === 'up' ? 'primary' : chg.direction === 'down' ? 'danger' : 'info'"
                                :timestamp="chg.from_period + ' → ' + chg.to_period">
                                <div>
                                    <span style="font-weight:bold;">ROE {{ chg.roe_change > 0 ? '↑' : '↓' }} {{ Math.abs(chg.roe_change).toFixed(2) }}pp</span>
                                    <el-tag v-for="(d, j) in chg.main_drivers" :key="j" size="small"
                                        :type="d.includes('↑') ? 'success' : d.includes('↓') ? 'danger' : 'info'"
                                        style="margin-left:6px;">{{ d }}</el-tag>
                                </div>
                                <!-- 财报评论 -->
                                <div v-if="getCommentary(chg.from_period, chg.to_period)" style="margin-top:8px;font-size:13px;color:#606266;line-height:1.6;background:#f8f9fa;padding:8px 12px;border-radius:6px;">
                                    <div>{{ getCommentary(chg.from_period, chg.to_period).commentary }}</div>
                                    <div v-if="getCommentary(chg.from_period, chg.to_period).details" style="margin-top:4px;display:flex;gap:10px;flex-wrap:wrap;">
                                        <el-tag v-if="getCommentary(chg.from_period, chg.to_period).details.revenue_yoy != null" size="small" effect="plain">
                                            营收同比{{ getCommentary(chg.from_period, chg.to_period).details.revenue_yoy?.toFixed(1) }}%
                                        </el-tag>
                                        <el-tag v-if="getCommentary(chg.from_period, chg.to_period).details.profit_yoy != null" size="small" effect="plain"
                                            :type="(getCommentary(chg.from_period, chg.to_period).details.profit_yoy||0) >= 0 ? 'success' : 'danger'">
                                            净利同比{{ getCommentary(chg.from_period, chg.to_period).details.profit_yoy?.toFixed(1) }}%
                                        </el-tag>
                                        <el-tag v-if="getCommentary(chg.from_period, chg.to_period).details.gross_margin != null" size="small" effect="plain">
                                            毛利率{{ getCommentary(chg.from_period, chg.to_period).details.gross_margin?.toFixed(2) }}%
                                        </el-tag>
                                        <el-tag v-if="getCommentary(chg.from_period, chg.to_period).details.eps != null" size="small" effect="plain">
                                            EPS={{ getCommentary(chg.from_period, chg.to_period).details.eps }}
                                        </el-tag>
                                    </div>
                                </div>
                            </el-timeline-item>
                        </el-timeline>
                    </el-card>
                </template>
                <el-empty v-else-if="!dupontLoading" description="暂无杜邦分析数据" />
            </el-tab-pane>

            <!-- Tab 4: 行业前瞻 -->
            <el-tab-pane label="🔭 行业前瞻" name="industry">
                <template v-if="fundData?.industry_outlook">
                    <el-card shadow="hover" style="margin-bottom:16px;">
                        <template #header><b>{{ fundData.industry_outlook.sector }}</b></template>
                        <el-descriptions :column="3" border size="small">
                            <el-descriptions-item label="板块排名">
                                <el-tag :type="(fundData.industry_outlook.rank||0) <= 20 ? 'success' : (fundData.industry_outlook.rank||0) <= 60 ? 'warning' : 'info'" size="small">
                                    #{{ fundData.industry_outlook.rank }}/{{ fundData.industry_outlook.total_sectors }}
                                </el-tag>
                            </el-descriptions-item>
                            <el-descriptions-item label="平均涨幅">
                                <span :style="{ color: (fundData.industry_outlook.avg_change||0) >= 0 ? '#f56c6c' : '#67c23a' }">{{ fundData.industry_outlook.avg_change }}%</span>
                            </el-descriptions-item>
                            <el-descriptions-item label="上涨占比">{{ fundData.industry_outlook.up_ratio }}%</el-descriptions-item>
                            <el-descriptions-item label="成份股数">{{ fundData.industry_outlook.stock_count }} 只</el-descriptions-item>
                            <el-descriptions-item label="走势">
                                <el-tag :type="(fundData.industry_outlook.avg_change||0) >= 1 ? 'danger' : (fundData.industry_outlook.avg_change||0) <= -1 ? 'success' : 'info'" size="small">
                                    {{ (fundData.industry_outlook.avg_change||0) >= 1 ? '🔥 强势' : (fundData.industry_outlook.avg_change||0) <= -1 ? '❄️ 弱势' : '→ 震荡' }}
                                </el-tag>
                            </el-descriptions-item>
                        </el-descriptions>
                    </el-card>
                    <el-card shadow="hover">
                        <template #header><b>🏆 板块龙头股</b></template>
                        <el-table :data="fundData.industry_outlook.top_stocks || []" border size="small" style="width:100%">
                            <el-table-column prop="name" label="名称" width="120" />
                            <el-table-column prop="price" label="现价" width="100">
                                <template #default="{ row }">{{ row.price?.toFixed(2) }}</template>
                            </el-table-column>
                            <el-table-column prop="change_pct" label="涨幅" width="100">
                                <template #default="{ row }">
                                    <span :style="{ color: row.change_pct >= 0 ? '#f56c6c' : '#67c23a' }">{{ row.change_pct >= 0 ? '+' : '' }}{{ row.change_pct?.toFixed(2) }}%</span>
                                </template>
                            </el-table-column>
                            <el-table-column prop="market_cap" label="总市值(亿)" width="120">
                                <template #default="{ row }">{{ row.market_cap?.toFixed(0) }}</template>
                            </el-table-column>
                            <el-table-column prop="code" label="代码" width="100" />
                        </el-table>
                    </el-card>
                </template>
                <el-empty v-else description="暂无行业数据" />
            </el-tab-pane>

            <!-- Tab 4: 档案 -->
            <el-tab-pane label="📁 档案" name="archive">
                <div v-if="archiveLoading" style="text-align:center;padding:40px;"><el-icon class="is-loading" :size="32"><Loading /></el-icon></div>
                <template v-else-if="archiveData">
                    <el-card shadow="hover" style="margin-bottom:16px;">
                        <template #header>
                            <div style="display:flex;justify-content:space-between;align-items:center;">
                                <b>📋 {{ archiveData.code }} {{ archiveData.name }}</b>
                                <el-tag v-if="archiveData.risk_passed === true" type="success">✅ 风控通过</el-tag>
                                <el-tag v-else-if="archiveData.risk_passed === false" type="danger">❌ 禁止买入</el-tag>
                            </div>
                        </template>
                        <el-descriptions :column="4" border size="small">
                            <el-descriptions-item label="行业">{{ archiveData.sector }}</el-descriptions-item>
                            <el-descriptions-item label="最新价">{{ archiveData.price }}</el-descriptions-item>
                            <el-descriptions-item label="涨跌幅">
                                <span :style="{ color: (archiveData.change_pct||0) >= 0 ? '#f56c6c' : '#67c23a' }">{{ archiveData.change_pct }}%</span>
                            </el-descriptions-item>
                            <el-descriptions-item label="RSI14">{{ archiveData.rsi14 }}</el-descriptions-item>
                            <el-descriptions-item label="均线多头">
                                <el-tag :type="archiveData.bullish_alignment ? 'success' : 'info'" size="small">{{ archiveData.bullish_alignment ? '是' : '否' }}</el-tag>
                            </el-descriptions-item>
                            <el-descriptions-item label="最新财报">{{ archiveData.latest_report || '--' }}</el-descriptions-item>
                            <el-descriptions-item label="营收(亿)">{{ archiveData.revenue || '--' }}</el-descriptions-item>
                            <el-descriptions-item label="净利(亿)">{{ archiveData.net_profit || '--' }}</el-descriptions-item>
                            <el-descriptions-item label="毛利率">{{ archiveData.gross_margin ? archiveData.gross_margin+'%' : '--' }}</el-descriptions-item>
                            <el-descriptions-item label="ROE">{{ archiveData.roe ? archiveData.roe+'%' : '--' }}</el-descriptions-item>
                            <el-descriptions-item label="EPS">{{ archiveData.eps || '--' }}</el-descriptions-item>
                            <el-descriptions-item label="负债率">{{ archiveData.debt_ratio ? archiveData.debt_ratio+'%' : '--' }}</el-descriptions-item>
                        </el-descriptions>
                    </el-card>
                    <el-card v-if="archiveData.business" shadow="hover" style="margin-bottom:16px;">
                        <template #header><b>🏭 主营业务</b></template>
                        <p style="font-size:13px;line-height:1.6;color:#303133;">{{ archiveData.business }}</p>
                    </el-card>
                    <el-card v-if="archiveData.industry_rank" shadow="hover" style="margin-bottom:16px;">
                        <template #header><b>🔭 行业排名</b></template>
                        <el-descriptions :column="3" border size="small">
                            <el-descriptions-item label="板块排名">#{{ archiveData.industry_rank }}/{{ archiveData.industry_total }}</el-descriptions-item>
                            <el-descriptions-item label="平均涨幅">{{ archiveData.industry_avg_chg }}%</el-descriptions-item>
                            <el-descriptions-item label="龙头股">{{ (archiveData.top_stocks||[]).map(s=>s.name).join('、') || '--' }}</el-descriptions-item>
                        </el-descriptions>
                    </el-card>
                    <el-card v-if="archiveData.analysis_history?.length" shadow="hover" style="margin-bottom:16px;">
                        <template #header><b>📅 分析历史（{{ archiveData.analysis_history.length }}次）</b></template>
                        <el-table :data="archiveData.analysis_history" border size="small" style="width:100%">
                            <el-table-column prop="analysis_date" label="日期" width="100" />
                            <el-table-column prop="price" label="当时价" width="70" />
                            <el-table-column prop="change_pct" label="涨幅" width="70">
                                <template #default="{ row }">
                                    <span :style="{ color: (row?.change_pct||0) >= 0 ? '#f56c6c' : '#67c23a' }">{{ row?.change_pct ?? 0 }}%</span>
                                </template>
                            </el-table-column>
                            <el-table-column prop="ma5" label="MA5" width="65" />
                            <el-table-column prop="ma20" label="MA20" width="65" />
                            <el-table-column prop="rsi14" label="RSI" width="55" />
                            <el-table-column prop="revenue" label="营收" width="65" />
                            <el-table-column prop="net_profit" label="净利" width="65" />
                            <el-table-column label="风控" width="65">
                                <template #default="{ row }">
<el-tag :type="row?.risk_passed ? 'success' : 'danger'" size="small">{{ row?.risk_passed ? '通过' : '禁止' }}</el-tag>
                                </template>
                            </el-table-column>
                            <el-table-column label="均线" width="55">
                                <template #default="{ row }">
                                    <el-tag v-if="row?.bullish_alignment" type="success" size="small">多头</el-tag>
                                    <el-tag v-else type="info" size="small">空头</el-tag>
                                </template>
                            </el-table-column>
                        </el-table>
                    </el-card>
                    <el-card shadow="hover">
                        <template #header>
                            <div style="display:flex;justify-content:space-between;align-items:center;">
                                <b>📝 备注</b>
                                <el-button size="small" type="primary" @click="showNoteDialog = true">添加备注</el-button>
                            </div>
                        </template>
                        <div v-if="!archiveData.notes?.length" style="color:#909399;text-align:center;padding:12px;">暂无备注</div>
                        <div v-for="(n, i) in archiveData.notes" :key="i" class="note-item">
                            <div class="note-text">{{ n.note }}</div>
                            <div class="note-time">{{ n.created_at }}</div>
                        </div>
                    </el-card>

                    <!-- 财报记录 -->
                    <el-card v-if="archiveData.financial_records?.length" shadow="hover" style="margin-top:16px;">
                        <template #header>
                            <div style="display:flex;justify-content:space-between;align-items:center;">
                                <b>📋 财务报表（{{ archiveData.financial_records.length }}期）</b>
                            </div>
                        </template>
                        <el-table :data="archiveData.financial_records" border size="small" style="width:100%"
                            :default-sort="{ prop: 'period', order: 'descending' }">
                            <el-table-column label="报告期" width="110" sortable>
                                <template #default="{ row }">{{ row?.period ?? row?.['报告期'] ?? '--' }}</template>
                            </el-table-column>
                            <el-table-column label="营收(亿)" width="80">
                                <template #default="{ row }">{{ formatFin(row?.revenue ?? row?.['营业总收入']) }}</template>
                            </el-table-column>
                            <el-table-column label="营收同比" width="75">
                                <template #default="{ row }">
                                    <span :style="{ color: (Number(row?.revenue_yoy ?? row?.['营业总收入同比增长率'])||0) >= 0 ? '#f56c6c' : '#67c23a' }">
                                        {{ formatFin(row.revenue_yoy || row['营业总收入同比增长率']) }}
                                    </span>
                                </template>
                            </el-table-column>
                            <el-table-column label="净利(亿)" width="80">
                                <template #default="{ row }">{{ formatFin(row?.net_profit ?? row?.['净利润']) }}</template>
                            </el-table-column>
                            <el-table-column label="净利同比" width="75">
                                <template #default="{ row }">
                                    <span :style="{ color: (Number(row?.net_profit_yoy ?? row?.['净利润同比增长率'])||0) >= 0 ? '#f56c6c' : '#67c23a' }">
                                        {{ formatFin(row.net_profit_yoy || row['净利润同比增长率']) }}
                                    </span>
                                </template>
                            </el-table-column>
                            <el-table-column label="毛利率" width="70">
                                <template #default="{ row }">{{ row?.gross_margin ?? row?.['销售毛利率'] ?? '--' }}</template>
                            </el-table-column>
                            <el-table-column label="ROE" width="65">
                                <template #default="{ row }">{{ row?.roe ?? row?.['净资产收益率'] ?? '--' }}</template>
                            </el-table-column>
                            <el-table-column label="EPS" width="60">
                                <template #default="{ row }">{{ row?.eps ?? row?.['基本每股收益'] ?? '--' }}</template>
                            </el-table-column>
                            <el-table-column label="BPS" width="60">
                                <template #default="{ row }">{{ row?.bps ?? row?.['每股净资产'] ?? '--' }}</template>
                            </el-table-column>
                        </el-table>
                    </el-card>

                    <!-- AI 分析（由AI整理对话记录生成） -->
                    <el-card shadow="hover" style="margin-top:16px;">
                        <template #header>
                            <div style="display:flex;justify-content:space-between;align-items:center;">
                                <b>🤖 AI 分析</b>
                                <div>
                                    <el-button v-if="aiAnalyses.length" size="small" type="danger" plain @click="clearAiAnalyses">清空</el-button>
                                    <el-button size="small" type="primary" @click="generateAiAnalysis" :loading="aiAnalyzing" style="margin-left:8px;">
                                        {{ aiAnalyzing ? '整理中...' : '生成AI分析' }}
                                    </el-button>
                                </div>
                            </div>
                        </template>

                        <!-- 已有分析记录 -->
                        <div v-if="aiAnalyses.length">
                            <div v-for="(item, i) in aiAnalyses" :key="i" class="ai-analysis-item">
                                <div class="ai-analysis-header">
                                    <el-tag type="success" size="mini" effect="dark">分析 #{{ aiAnalyses.length - i }}</el-tag>
                                    <span class="ai-analysis-time">{{ item.created_at }}</span>
                                    <span style="color:#909399;font-size:11px;">基于 {{ item.chat_count }} 轮对话</span>
                                </div>
                                <div class="ai-analysis-body" v-html="renderMarkdown(item.summary)"></div>
                            </div>
                        </div>

                        <!-- 空状态 + 引导 -->
                        <div v-else-if="!aiAnalyzing" style="text-align:center;padding:24px;color:#909399;font-size:13px;">
                            <p>先跟 AI 助手聊这只股票，然后点击「生成AI分析」</p>
                            <p style="margin-top:6px;">AI 会把对话内容整理成技术面、基本面、风险提示等要点</p>
                        </div>
                        <div v-else style="text-align:center;padding:40px;">
                            <el-icon class="is-loading" :size="28"><Loading /></el-icon>
                            <p style="color:#909399;margin-top:8px;">正在整理对话记录...</p>
                        </div>
                    </el-card>
                </template>
                <el-empty v-else description="点击上方「深度分析」后自动生成档案" />
            </el-tab-pane>
        </el-tabs>

        <el-empty v-if="!loading && !result" description="输入股票代码，点击分析" style="margin-top:40px;" />

        <!-- 备注对话框 -->
        <el-dialog v-model="showNoteDialog" title="添加备注" width="400px">
            <el-input v-model="newNote" type="textarea" :rows="4" placeholder="输入对这只股票的观察、判断、交易计划..." />
            <template #footer>
                <el-button @click="showNoteDialog = false">取消</el-button>
                <el-button type="primary" @click="saveNote">保存</el-button>
            </template>
        </el-dialog>

        <!-- ==================== AI 聊天对话框 ==================== -->
        <!-- 浮动按钮 -->
        <div v-if="result" class="chat-fab" @click="chatOpen = !chatOpen">
            <span v-if="!chatOpen">💬</span>
            <span v-else>✕</span>
        </div>

        <!-- 聊天面板 -->
        <Transition name="chat-slide">
            <div v-if="chatOpen && result" class="chat-panel">
                <div class="chat-header">
                    <b>🤖 AI 投研助手</b>
                    <span style="font-size:11px;color:#909399;">{{ result.name }} ({{ result.code }})</span>
                    <el-button size="small" link @click="chatOpen = false" style="margin-left:auto;color:#909399;">✕</el-button>
                </div>
                <div class="chat-messages" ref="chatRef">
                    <div v-if="!chatMessages.length" class="chat-welcome">
                        <p>你好！我是 AI 投研助手 🤖</p>
                        <p>有什么关于 <b>{{ result.name }}</b> 的问题可以问我，比如：</p>
                        <div class="chat-suggestions">
                            <div v-for="q in sampleQuestions" :key="q" class="suggestion-tag" @click="sendMessage(q)">{{ q }}</div>
                        </div>
                    </div>
                    <div v-for="(msg, i) in chatMessages" :key="i"
                        class="chat-msg"
                        :class="msg.role === 'user' ? 'chat-msg-user' : 'chat-msg-ai'">
                        <div class="chat-msg-content">{{ msg.content }}</div>
                    </div>
                    <div v-if="chatLoading" class="chat-msg chat-msg-ai">
                        <div class="chat-msg-content chat-typing">思考中<span>.</span><span>.</span><span>.</span></div>
                    </div>
                </div>
                <div class="chat-input-area">
                    <el-input v-model="chatInput" placeholder="输入问题，按 Enter 发送..."
                        size="small" clearable
                        @keyup.enter="sendMessage(chatInput)"
                        :disabled="chatLoading" />
                    <el-button type="primary" size="small" @click="sendMessage(chatInput)"
                        :loading="chatLoading" :disabled="!chatInput.trim()" style="margin-left:8px;flex-shrink:0;">
                        发送
                    </el-button>
                </div>
            </div>
        </Transition>
    </div>

    <!-- 详细财报弹窗 -->
    <el-dialog v-model="statementsVisible" title="📄 三张财务报表" width="90%" top="5vh"
        :close-on-click-modal="false" @open="loadStatements">
        <div v-if="statementsLoading" style="text-align:center;padding:40px;">
            <el-icon class="is-loading" :size="32"><Loading /></el-icon>
            <p style="color:#909399;margin-top:8px;">加载财务报表...</p>
        </div>
        <template v-else-if="statementsData">
            <!-- 财报健康评分卡 -->
            <div v-if="statementsData.health_score" style="margin-bottom:16px;padding:16px;border-radius:8px;border:1px solid #334;"
                :style="{ background: statementsData.health_score.total_pct >= 65 ? 'linear-gradient(135deg, #1a2e1a, #1a1a2e)' : statementsData.health_score.total_pct >= 45 ? 'linear-gradient(135deg, #2e2a1a, #1a1a2e)' : 'linear-gradient(135deg, #2e1a1a, #1a1a2e)' }">
                <div style="display:flex;align-items:center;justify-content:space-between;flex-wrap:wrap;gap:8px;margin-bottom:12px;">
                    <div style="display:flex;align-items:center;gap:12px;">
                        <span style="font-size:28px;">{{ statementsData.health_score.emoji }}</span>
                        <div>
                            <span style="font-size:20px;font-weight:bold;color:#e0e0e0;">财报健康评分</span>
                            <span style="font-size:24px;font-weight:bold;margin-left:12px;color:#409eff;">{{ statementsData.health_score.total_score }}</span>
                            <span style="color:#909399;font-size:14px;">/ {{ statementsData.health_score.total_max }}</span>
                            <el-tag :type="statementsData.health_score.total_pct >= 65 ? 'success' : statementsData.health_score.total_pct >= 45 ? 'warning' : 'danger'"
                                style="margin-left:8px;font-size:13px;font-weight:bold;">
                                {{ statementsData.health_score.overall }}
                            </el-tag>
                        </div>
                    </div>
                    <div style="font-size:28px;font-weight:bold;color:#e0e0e0;">
                        {{ statementsData.health_score.total_pct }}<span style="font-size:16px;color:#909399;">%</span>
                    </div>
                </div>
                <!-- 各维度评分 -->
                <div style="display:grid;grid-template-columns:repeat(auto-fit, minmax(220px, 1fr));gap:10px;">
                    <div v-for="dim in statementsData.health_score.dimensions" :key="dim.name"
                        style="background:rgba(255,255,255,0.04);border-radius:6px;padding:10px 12px;border:1px solid rgba(255,255,255,0.06);">
                        <div style="display:flex;align-items:center;justify-content:space-between;margin-bottom:6px;">
                            <span style="font-size:13px;color:#ccc;">{{ dim.icon }} {{ dim.name }}</span>
                            <span :style="{ color: dim.score >= dim.max * 0.65 ? '#67c23a' : dim.score >= dim.max * 0.45 ? '#e6a23c' : '#f56c6c', fontWeight:'bold', fontSize:'14px' }">
                                {{ dim.score }}/{{ dim.max }}
                            </span>
                        </div>
                        <!-- 进度条 -->
                        <div style="height:5px;background:rgba(255,255,255,0.08);border-radius:3px;overflow:hidden;margin-bottom:6px;">
                            <div :style="{ width: (dim.score/dim.max*100)+'%', height:'100%', background: dim.score >= dim.max * 0.65 ? '#67c23a' : dim.score >= dim.max * 0.45 ? '#e6a23c' : '#f56c6c', borderRadius:'3px', transition:'width 0.5s' }"></div>
                        </div>
                        <!-- 子项折叠 -->
                        <div v-for="(d, di) in dim.details" :key="di" style="font-size:11px;color:#909399;margin-top:4px;padding:3px 4px;border-radius:3px;background:rgba(255,255,255,0.03);">
                            <div style="display:flex;justify-content:space-between;align-items:center;">
                                <span>{{ d.item }}</span>
                                <span :style="{ color: d.score >= d.max * 0.65 ? '#67c23a' : '#e6a23c', fontWeight:'bold' }">
                                    {{ d.value }}
                                </span>
                            </div>
                            <div style="font-size:10px;color:#666;line-height:1.4;">
                                {{ d.desc }} → <span :style="{ color: d.score >= d.max * 0.65 ? '#67c23a' : d.score >= d.max * 0.45 ? '#e6a23c' : '#f56c6c' }">{{ d.verdict }}</span>
                            </div>
                        </div>
                    </div>
                </div>
            </div>
            <el-tabs type="border-card">
                <el-tab-pane label="📊 利润表">
                    <el-table :data="statementsData.profit_sheet || []" border size="small" style="width:100%"
                        :default-sort="{ prop: 'period', order: 'descending' }">
                        <el-table-column prop="period" label="报告期" width="110" sortable fixed />
                        <el-table-column v-for="col in getStatementFields('profit_sheet')" :key="col" :label="col" width="120">
                            <template #default="{ row }">{{ formatVal(row.items?.[col]) }}</template>
                        </el-table-column>
                    </el-table>
                </el-tab-pane>
                <el-tab-pane label="🏛️ 资产负债表">
                    <el-table :data="statementsData.balance_sheet || []" border size="small" style="width:100%"
                        :default-sort="{ prop: 'period', order: 'descending' }">
                        <el-table-column prop="period" label="报告期" width="110" sortable fixed />
                        <el-table-column v-for="col in getStatementFields('balance_sheet')" :key="col" :label="col" width="120">
                            <template #default="{ row }">{{ formatVal(row.items?.[col]) }}</template>
                        </el-table-column>
                    </el-table>
                </el-tab-pane>
                <el-tab-pane label="💵 现金流量表">
                    <el-table :data="statementsData.cash_flow || []" border size="small" style="width:100%"
                        :default-sort="{ prop: 'period', order: 'descending' }">
                        <el-table-column prop="period" label="报告期" width="110" sortable fixed />
                        <el-table-column v-for="col in getStatementFields('cash_flow')" :key="col" :label="col" width="140">
                            <template #default="{ row }">{{ formatVal(row.items?.[col]) }}</template>
                        </el-table-column>
                    </el-table>
                </el-tab-pane>
            </el-tabs>
        </template>
        <el-empty v-else description="暂无财务报表数据" />
    </el-dialog>
</template>

<script setup>
import { ref, computed, onMounted, nextTick, watch, onBeforeUnmount, inject } from 'vue'
import { analyzeStock, getFundamental, getStockProfile, addStockNote, chatWithAI, summarizeChat, getAiAnalyses, clearAiAnalyses as apiClearAi, searchStockInfo, addWatchItem, getWatchlist, getLocalKline, getDupontAnalysis, getDupontCommentary, getExpenseAnalysis, getFinancialStatements, getComprehensiveAnalysis } from '../api/index.js'
import { ElMessage } from 'element-plus'
import { useRoute, useRouter } from 'vue-router'
import * as echarts from 'echarts'

const route = useRoute()
const router = useRouter()
const stockName = inject('stockName')
const pageStockCode = inject('stockCode')

const stockCode = ref('')
const loading = ref(false)
const result = ref(null)
const activeTab = ref('tech')

// 合并风控数据源，只显示未通过
const allFailedRules = computed(() => {
    const r = result.value
    const checks = []
    if (r?.custom_risk) checks.push(...r.custom_risk.filter(c => c.status !== 'pass'))
    return checks
})

const fundData = ref(null)
const fundLoading = ref(false)
const expenseData = ref(null)
const expenseLoading = ref(false)
const statementsVisible = ref(false)
const statementsLoading = ref(false)
const statementsData = ref(null)
const comprehensiveData = ref(null)
const comprehensiveLoading = ref(false)

function rawReportRows(raw) {
    if (!raw) return []
    const map = [
        { key: '报告期', item: '报告期', source: '--', desc: '财报截止日期' },
        { key: '营业总收入', item: '营业收入', source: '利润表', desc: '净利润=营收-成本-费用' },
        { key: '营业成本', item: '营业成本', source: '利润表', desc: '' },
        { key: '净利润', item: '净利润', source: '利润表', desc: '归母+少数股东损益' },
        { key: '归母净利润', item: '归母净利润', source: '利润表', desc: '归属母公司股东的利润' },
        { key: '销售费用', item: '销售费用', source: '利润表', desc: '三项费用之一' },
        { key: '管理费用', item: '管理费用', source: '利润表', desc: '三项费用之一' },
        { key: '研发费用', item: '研发费用', source: '利润表', desc: '' },
        { key: '财务费用', item: '财务费用', source: '利润表', desc: '三项费用之一' },
        { key: '上期营收', item: '上期营收', source: '利润表', desc: '用于计算营收增长率' },
        { key: '上期净利润', item: '上期净利润', source: '利润表', desc: '用于计算利润增长率' },
        { key: '资产总计', item: '资产总计', source: '资产负债表', desc: '负债+股东权益' },
        { key: '负债合计', item: '负债合计', source: '资产负债表', desc: '资产负债率=负债/资产' },
        { key: '股东权益', item: '股东权益', source: '资产负债表', desc: 'ROE=净利润/股东权益' },
        { key: '流动资产', item: '流动资产', source: '资产负债表', desc: '流动比率=流动资产/流动负债' },
        { key: '流动负债', item: '流动负债', source: '资产负债表', desc: '' },
        { key: '货币资金', item: '货币资金', source: '资产负债表', desc: '现金短债比=货币资金/短借' },
        { key: '应收账款', item: '应收账款', source: '资产负债表', desc: '应收周转率=营收/应收' },
        { key: '存货', item: '存货', source: '资产负债表', desc: '存货周转率=成本/存货' },
        { key: '短期借款', item: '短期借款', source: '资产负债表', desc: '' },
        { key: '长期借款', item: '长期借款', source: '资产负债表', desc: '' },
        { key: '固定资产', item: '固定资产', source: '资产负债表', desc: '' },
        { key: '经营现金流', item: '经营现金流', source: '现金流量表', desc: '造血能力、OCF/净利润比' },
        { key: '投资现金流', item: '投资现金流', source: '现金流量表', desc: '负数=扩张投资' },
        { key: '筹资现金流', item: '筹资现金流', source: '现金流量表', desc: '正数=借款/增发' },
        { key: '销售毛利率', item: '毛利率 %', source: '财务摘要', desc: '(营收-成本)/营收' },
        { key: '销售净利率', item: '净利率 %', source: '财务摘要', desc: '净利润/营收' },
        { key: '净资产收益率_ROE', item: 'ROE %', source: '财务摘要', desc: '净利润/股东权益' },
        { key: '资产负债率', item: '资产负债率 %', source: '财务摘要', desc: '负债/资产' },
        { key: '基本每股收益', item: 'EPS', source: '财务摘要', desc: '元/股' },
        { key: '每股净资产', item: '每股净资产', source: '财务摘要', desc: '元' },
        { key: '每股经营现金流', item: '每股经营现金流', source: '财务摘要', desc: '元' },
    ]
    return map.map(m => ({ item: m.item, value: raw[m.key], source: m.source, desc: m.desc }))
}

function getStatementFields(type) {
    const rows = statementsData.value?.[type] || []
    if (!rows.length) return []
    // Collect all unique field names across all periods
    const fields = new Set()
    rows.forEach(r => Object.keys(r.items || {}).forEach(k => fields.add(k)))
    return Array.from(fields)
}
function formatVal(v) {
    if (v == null || v === '' || v === '--') return '--'
    if (typeof v === 'number') {
        if (v >= 0) return v.toFixed(2)
        return v.toFixed(2)
    }
    return v
}
async function loadStatements() {
    const code = result.value?.code
    if (!code || statementsData.value) return
    statementsLoading.value = true
    try {
        const { data } = await getFinancialStatements(code)
        statementsData.value = data
    } catch (e) {
        console.error('财报加载失败', e)
    } finally {
        statementsLoading.value = false
    }
}
async function loadComprehensiveData() {
    const code = result.value?.code
    if (!code) return
    comprehensiveLoading.value = true
    try {
        const { data } = await getComprehensiveAnalysis(code)
        comprehensiveData.value = data
    } catch (e) {
        console.error('综合评估加载失败', e)
    } finally {
        comprehensiveLoading.value = false
    }
}
const dupontData = ref(null)
const dupontLoading = ref(false)
const dupontCommentary = ref([])
const archiveData = ref(null)
const archiveLoading = ref(false)
const showNoteDialog = ref(false)
const newNote = ref('')
const inWatchlist = ref(false)
const watchlistLoading = ref(false)

const t = computed(() => ({ tech: result.value?.technical || {} }))

const selectedStock = ref('')

// ===== K线图表 =====
const klineChartRef = ref(null)
let klineChartInstance = null
const klineLoading = ref(false)

function calcSMA(data, period) {
    const result = []
    for (let i = 0; i < data.length; i++) {
        if (i < period - 1) { result.push(NaN); continue }
        let sum = 0
        for (let j = i - period + 1; j <= i; j++) sum += data[j]
        result.push(+(sum / period).toFixed(2))
    }
    return result
}

function calcEMA(data, period) {
    const k = 2 / (period + 1)
    const result = []
    let ema = data[0]
    for (let i = 0; i < data.length; i++) {
        ema = i === 0 ? data[i] : data[i] * k + ema * (1 - k)
        result.push(+(ema).toFixed(4))
    }
    return result
}

function calcMACD(close) {
    const dif = calcEMA(close, 12)
    // DEA = EMA(DIF, 9)
    const dea = []
    let ema_dea = dif[0]
    const k_dea = 2 / (9 + 1)
    for (let i = 0; i < dif.length; i++) {
        ema_dea = i === 0 ? dif[i] : dif[i] * k_dea + ema_dea * (1 - k_dea)
        dea.push(+(ema_dea).toFixed(4))
    }
    // MACD柱 = (DIF - DEA) * 2
    const macd = dif.map((d, i) => +((d - dea[i]) * 2).toFixed(4))
    return { dif, dea, macd }
}

async function loadKlineChart() {
    if (!result.value?.code) return
    let data
    klineLoading.value = true
    try {
        const resp = await getLocalKline(result.value.code, 200)
        data = resp.data
        const recs = data.records || []
        if (recs.length < 20) { klineLoading.value = false; return }

        const dates = recs.map(r => r.date.slice(5, 10))
        const opens = recs.map(r => r.open)
        const closes = recs.map(r => r.close)
        const highs = recs.map(r => r.high)
        const lows = recs.map(r => r.low)
        const vols = recs.map(r => r.volume)

        const ma5 = calcSMA(closes, 5)
        const ma10 = calcSMA(closes, 10)
        const ma20 = calcSMA(closes, 20)
        const ma60 = calcSMA(closes, 60)

        const { dif, dea, macd } = calcMACD(closes)

        // 构建MACD柱图数据：正值红色，负值绿色
        const macdBarData = macd.map(v => ({
            value: +v.toFixed(4),
            itemStyle: { color: v >= 0 ? '#f56c6c' : '#67c23a' },
        }))

        await nextTick()
        if (!klineChartRef.value) { klineLoading.value = false; return }

        // 等DOM完全稳定后再初始化图表
        await new Promise(r => setTimeout(r, 100))

        if (klineChartInstance) klineChartInstance.dispose()
        klineChartInstance = echarts.init(klineChartRef.value, null, { renderer: 'canvas' })

        const option = {
            backgroundColor: '#1a1a2e',
            animation: false,
            grid: [
                { left: '6%', right: '3%', top: '4%', height: '58%' },
                { left: '6%', right: '3%', top: '72%', height: '18%' },
            ],
            xAxis: [
                { type: 'category', data: dates, gridIndex: 0,
                    axisLabel: { color: '#909399', fontSize: 10, interval: 20 },
                    axisLine: { lineStyle: { color: '#334' } },
                    splitLine: { show: false } },
                { type: 'category', data: dates, gridIndex: 1,
                    axisLabel: { show: false },
                    axisLine: { lineStyle: { color: '#334' } },
                    splitLine: { show: false } },
            ],
            yAxis: [
                { type: 'value', gridIndex: 0, scale: true,
                    axisLabel: { color: '#909399', fontSize: 10 },
                    splitLine: { lineStyle: { color: '#2a2a3e' } } },
                { type: 'value', gridIndex: 1, scale: true,
                    axisLabel: { color: '#909399', fontSize: 10 },
                    splitLine: { lineStyle: { color: '#2a2a3e' } } },
            ],
            dataZoom: [
                { type: 'inside', xAxisIndex: [0, 1], start: 40, end: 100 },
                { type: 'slider', xAxisIndex: [0, 1], start: 40, end: 100,
                    height: 16, bottom: 2,
                    borderColor: '#334', backgroundColor: '#1a1a2e',
                    fillerColor: 'rgba(64,158,255,0.2)',
                    textStyle: { color: '#909399', fontSize: 9 } },
            ],
            tooltip: {
                trigger: 'axis',
                axisPointer: { type: 'cross' },
                backgroundColor: 'rgba(30,30,50,0.95)',
                borderColor: '#409eff',
                textStyle: { color: '#e0e0e0', fontSize: 11 },
            },
            series: [
                // 蜡烛图
                {
                    name: '日K', type: 'candlestick', xAxisIndex: 0, yAxisIndex: 0,
                    data: recs.map(r => [+r.open, +r.close, +r.low, +r.high]),
                    itemStyle: {
                        color: '#f56c6c', color0: '#67c23a',
                        borderColor: '#f56c6c', borderColor0: '#67c23a',
                    },
                },
                // MA5
                { name: 'MA5', type: 'line', xAxisIndex: 0, yAxisIndex: 0,
                    data: ma5, smooth: true, symbol: 'none',
                    lineStyle: { width: 1, color: '#e6a23c' } },
                // MA10
                { name: 'MA10', type: 'line', xAxisIndex: 0, yAxisIndex: 0,
                    data: ma10, smooth: true, symbol: 'none',
                    lineStyle: { width: 1, color: '#409eff' } },
                // MA20
                { name: 'MA20', type: 'line', xAxisIndex: 0, yAxisIndex: 0,
                    data: ma20, smooth: true, symbol: 'none',
                    lineStyle: { width: 1, color: '#b37feb' } },
                // MA60
                { name: 'MA60', type: 'line', xAxisIndex: 0, yAxisIndex: 0,
                    data: ma60, smooth: true, symbol: 'none',
                    lineStyle: { width: 1, color: '#ff85c0' } },
                // MACD柱状图
                {
                    name: 'MACD', type: 'bar', xAxisIndex: 1, yAxisIndex: 1,
                    data: macdBarData,
                },
                // DIF线
                { name: 'DIF', type: 'line', xAxisIndex: 1, yAxisIndex: 1,
                    data: dif, smooth: true, symbol: 'none',
                    lineStyle: { width: 1, color: '#fff' } },
                // DEA线
                { name: 'DEA', type: 'line', xAxisIndex: 1, yAxisIndex: 1,
                    data: dea, smooth: true, symbol: 'none',
                    lineStyle: { width: 1, color: '#ffd666' } },
            ],
            legend: {
                data: ['MA5', 'MA10', 'MA20', 'MA60', 'DIF', 'DEA'],
                top: 0, right: 10, textStyle: { color: '#ccc', fontSize: 11 },
                icon: 'roundRect',
            },
        }
        klineChartInstance.setOption(option)
    } catch (e) {
        console.error('K线图加载失败', e)
        console.log('Kline chart error details:', {
            code: result.value?.code,
            recordsCount: data?.records?.length,
            klineChartRef: !!klineChartRef.value,
        })
    } finally {
        klineLoading.value = false
    }
}

// ===== 杜邦分析 =====
const latestRow = computed(() => {
    const rows = dupontData.value?.dupont?.rows
    return rows?.length ? rows[rows.length - 1] : null
})

function getCommentary(fromPeriod, toPeriod) {
    return dupontCommentary.value.find(c => c.from_period === fromPeriod && c.to_period === toPeriod) || null
}

async function loadDupontData() {
    const code = result.value?.code
    if (!code) return
    dupontLoading.value = true
    try {
        const { data } = await getDupontAnalysis(code)
        dupontData.value = data
        // 评论异步加载，不阻塞主数据展示
        getDupontCommentary(code).then(resp => {
            if (resp.data?.commentary) dupontCommentary.value = resp.data.commentary
        }).catch(() => {})
    } catch (e) {
        console.error('杜邦分析加载失败', e)
    } finally {
        dupontLoading.value = false
    }
}

// ===== 费用分析 =====
async function loadExpenseData() {
    const code = result.value?.code
    if (!code || expenseData.value) return
    expenseLoading.value = true
    try {
        const { data } = await getExpenseAnalysis(code)
        expenseData.value = data
    } catch (e) {
        console.error('费用分析加载失败', e)
    } finally {
        expenseLoading.value = false
    }
}

// 监听tab切换到K线时加载图表
watch(activeTab, (tab) => {
    if (tab === 'kline' && result.value?.code) {
        nextTick(() => loadKlineChart())
    }
    if (tab === 'dupont' && result.value?.code && !dupontData.value) {
        nextTick(() => loadDupontData())
    }
    if (tab === 'comprehensive' && result.value?.code && !comprehensiveData.value) {
        nextTick(() => loadComprehensiveData())
    }
    if (tab === 'fundamental' && result.value?.code && !expenseData.value) {
        nextTick(() => loadExpenseData())
    }
})
// 分析结果加载后，如果K线tab正激活则自动渲染图表
watch(result, (val) => {
    if (val?.code && activeTab.value === 'kline') {
        nextTick(() => loadKlineChart())
    }
    if (val?.code && activeTab.value === 'dupont' && !dupontData.value) {
        nextTick(() => loadDupontData())
    }
    if (val?.code && activeTab.value === 'comprehensive' && !comprehensiveData.value) {
        nextTick(() => loadComprehensiveData())
    }
    if (val?.code && activeTab.value === 'fundamental') {
        nextTick(() => {
            if (!fundData.value) loadFundamental(result.value?.code)
        })
    }
})

// 窗口resize自适应
function onTabClick(tab) {
    if (tab.props.name === 'kline') {
        nextTick(() => loadKlineChart())
    }
    if (tab.props.name === 'dupont' && result.value?.code && !dupontData.value) {
        nextTick(() => loadDupontData())
    }
    if (tab.props.name === 'comprehensive' && result.value?.code && !comprehensiveData.value) {
        nextTick(() => loadComprehensiveData())
    }
    if (tab.props.name === 'fundamental' && result.value?.code && !fundData.value) {
        nextTick(() => loadFundamental(result.value.code))
    }
}

let resizeHandler = null
onMounted(() => {
    resizeHandler = () => { klineChartInstance?.resize() }
    window.addEventListener('resize', resizeHandler)
})
onBeforeUnmount(() => {
    if (resizeHandler) window.removeEventListener('resize', resizeHandler)
    klineChartInstance?.dispose()
})

// 搜索建议
async function querySearch(query, cb) {
    if (!query || query.trim().length < 1) {
        cb([])
        return
    }
    try {
        const { data } = await searchStockInfo(query.trim())
        cb((data.results || []).map(r => ({
            value: `${r.code} ${r.name}`,
            code: r.code,
            name: r.name,
            market: r.market,
            industry: r.industry || '',
        })))
    } catch {
        cb([])
    }
}
function handleSelect(item) {
    stockCode.value = item.code
}

let _internalNav = false

// 支持从 URL 参数 ?code=XXXX 自动加载分析
onMounted(() => {
    const code = route.query.code
    if (code) {
        stockCode.value = code
        search()
    }
})

// 监听 URL 参数变化——处理浏览器前进后退、从其他页面跳转
watch(() => route.query.code, (newCode) => {
    if (_internalNav) { _internalNav = false; return }
    if (!newCode) return
    stockCode.value = newCode
    search()
})

async function search() {
    const code = stockCode.value?.trim()
    if (!code) {
        ElMessage.warning('请输入股票代码')
        return
    }
    // 同步URL参数，设置标记防止route watcher重复触发
    _internalNav = true
    router.replace({ query: { code } })
    loading.value = true
    result.value = null
    fundData.value = null
    archiveData.value = null
    dupontData.value = null
    expenseData.value = null
    statementsData.value = null
    comprehensiveData.value = null
    try {
        const { data } = await analyzeStock(code)
        result.value = data
        // 更新页面标题
        document.title = `${data.name} (${code}) - 个股分析 - AI投研助手`
        stockName.value = data.name
        pageStockCode.value = code
        // 并发加载基本面+档案
        loadFundamental(code)
        loadArchive(code)
    } catch (e) {
        ElMessage.error(e.response?.data?.detail || '分析失败')
    } finally {
        loading.value = false
    }
    // 检查是否已在观察池
    checkWatchlist(code)
}

async function checkWatchlist(code) {
    try {
        const { data } = await getWatchlist()
        inWatchlist.value = (data.items || []).some(i => i.code === code)
    } catch {
        inWatchlist.value = false
    }
}

async function addToWatchlist() {
    const code = stockCode.value?.trim()
    if (!code || !result.value?.name) return
    watchlistLoading.value = true
    try {
        await addWatchItem({
            code,
            name: result.value.name,
            sector: result.value.sector || result.value.industry || '',
        })
        inWatchlist.value = true
        ElMessage.success(`已添加 ${result.value.name} 到观察池`)
    } catch (e) {
        ElMessage.error(e.response?.data?.detail || '添加失败')
    } finally {
        watchlistLoading.value = false
    }
}

async function loadFundamental(code) {
    fundLoading.value = true
    try {
        const [fundResp, stmtResp] = await Promise.all([
            getFundamental(code),
            getFinancialStatements(code),
        ])
        fundData.value = fundResp.data
        statementsData.value = stmtResp.data
    } catch {} finally { fundLoading.value = false }
}

async function loadArchive(code) {
    archiveLoading.value = true
    try {
        const { data } = await getStockProfile(code)
        archiveData.value = data
    } catch {} finally { archiveLoading.value = false }
    loadAiAnalyses()
}

async function saveNote() {
    const code = stockCode.value?.trim()
    if (!code || !newNote.value?.trim()) {
        ElMessage.warning('请输入备注内容')
        return
    }
    try {
        await addStockNote(code, newNote.value.trim())
        ElMessage.success('备注已保存')
        showNoteDialog.value = false
        newNote.value = ''
        loadArchive(code)
    } catch (e) {
        ElMessage.error('保存失败')
    }
}

// ===== AI 分析（整理对话记录） =====
const aiAnalyses = ref([])
const aiAnalyzing = ref(false)

async function generateAiAnalysis() {
    const code = stockCode.value?.trim()
    if (!code) return
    if (!result.value?.name) {
        ElMessage.warning('请先分析股票')
        return
    }
    aiAnalyzing.value = true
    try {
        const { data } = await summarizeChat(code)
        if (data.summary && data.summary !== '暂无AI对话可供分析') {
            ElMessage.success('AI分析已生成')
        } else {
            ElMessage.info(data.summary || '暂无对话记录可分析')
        }
        await loadAiAnalyses()
    } catch (e) {
        ElMessage.error('生成失败')
    } finally {
        aiAnalyzing.value = false
    }
}

async function loadAiAnalyses() {
    const code = stockCode.value?.trim()
    if (!code) return
    try {
        const { data } = await getAiAnalyses(code, 5)
        aiAnalyses.value = data.records || []
    } catch {}
}

async function clearAiAnalyses() {
    const code = stockCode.value?.trim()
    if (!code) return
    try {
        await apiClearAi(code)
        aiAnalyses.value = []
        ElMessage.success('已清空')
    } catch {
        ElMessage.error('清空失败')
    }
}

function renderMarkdown(text) {
    if (!text) return ''
    let html = text
        .replace(/### (.+)/g, '<h4 style="margin:8px 0 4px;color:#303133;">$1</h4>')
        .replace(/## (.+)/g, '<h3 style="margin:10px 0 4px;color:#303133;">$1</h3>')
        .replace(/# (.+)/g, '<h2 style="margin:12px 0 4px;color:#303133;">$1</h2>')
        .replace(/\*\*(.+?)\*\*/g, '<strong>$1</strong>')
        .replace(/^- (.+)/gm, '<li style="margin:2px 0;">$1</li>')
        .replace(/\n\n/g, '<br>')
    return html
}

function formatFin(val) {
    if (val === null || val === undefined || val === '--' || val === '') return '--'
    return String(val)
}

// ===== AI 聊天 =====
const chatOpen = ref(false)
const chatInput = ref('')
const chatMessages = ref([])
const chatLoading = ref(false)
const chatRef = ref(null)

const sampleQuestions = [
    '这只股票技术面怎么样？',
    '风控检查哪些不合格？',
    '基本面数据如何？',
    '均线是多头排列吗？',
    '当前适合买入吗？',
]

async function sendMessage(text) {
    const msg = text?.trim()
    if (!msg) return
    if (!result.value?.code) return

    chatInput.value = ''
    chatMessages.value.push({ role: 'user', content: msg })
    chatLoading.value = true
    scrollChat()

    try {
        // 传最近的历史（最多最近5轮）
        const history = chatMessages.value.slice(-10, -1).map(m => ({
            role: m.role,
            content: m.content,
        }))
        const { data } = await chatWithAI(result.value.code, msg, history)
        chatMessages.value.push({ role: 'assistant', content: data.reply || '抱歉，暂时无法回答' })
    } catch {
        chatMessages.value.push({ role: 'assistant', content: '抱歉，网络错误，请稍后重试' })
    } finally {
        chatLoading.value = false
        scrollChat()
    }
}

function scrollChat() {
    nextTick(() => {
        const el = chatRef.value
        if (el) el.scrollTop = el.scrollHeight
    })
}
</script>

<style scoped>
.analysis-page { max-width: 1400px; margin: 0 auto; }
.risk-pass { background: #f0f9eb; }
.risk-warning { background: #fdf6ec; }
.risk-fail { background: #fef0f0; }
.risk-title { font-weight: bold; font-size: 14px; }
.risk-value { font-size: 12px; color: #606266; margin: 4px 0; }
.risk-status { margin-top: 8px; }
.news-item { padding: 8px 0; border-bottom: 1px solid #f0f0f0; }
.news-title { font-size: 13px; color: #303133; }
.news-title a { color: #409eff; text-decoration: none; }
.news-title a:hover { text-decoration: underline; }
.news-time { font-size: 12px; color: #909399; margin-top: 2px; }
.biz-item { padding: 4px 0; }
.biz-field { margin: 4px 0; font-size: 13px; line-height: 1.6; }
.biz-field label { color: #606266; font-weight: bold; margin-right: 4px; }
.note-item { padding: 8px 0; border-bottom: 1px solid #f0f0f0; }
.note-text { font-size: 13px; color: #303133; }
.note-time { font-size: 12px; color: #909399; margin-top: 2px; }
.pattern-bullish { border-left: 4px solid #f56c6c; }
.pattern-bearish { border-left: 4px solid #67c23a; }
.pattern-neutral { border-left: 4px solid #909399; }
.pattern-header { display: flex; align-items: center; gap: 4px; flex-wrap: wrap; margin-bottom: 8px; }
.pattern-name { font-weight: bold; font-size: 15px; color: #303133; }
.pattern-desc { font-size: 13px; color: #606266; line-height: 1.5; }

/* ===== AI 分析（档案页） ===== */
.ai-analysis-item {
    padding: 12px 0; border-bottom: 1px solid #f0f0f0;
}
.ai-analysis-item:last-child { border-bottom: none; }
.ai-analysis-header {
    display: flex; align-items: center; gap: 8px; margin-bottom: 8px;
}
.ai-analysis-time { font-size: 11px; color: #c0c4cc; }
.ai-analysis-body {
    font-size: 13px; line-height: 1.7; color: #303133;
    padding: 8px 12px; background: #f8f9fa; border-radius: 6px;
}
.ai-analysis-body li { list-style: none; padding: 1px 0; }
.ai-analysis-body li::before { content: '• '; color: #409eff; }

/* ===== AI 聊天 ===== */
.chat-fab {
    position: fixed; bottom: 28px; right: 28px;
    width: 52px; height: 52px; border-radius: 50%;
    background: #409eff; color: #fff;
    display: flex; align-items: center; justify-content: center;
    font-size: 22px; cursor: pointer;
    box-shadow: 0 4px 16px rgba(64,158,255,0.35);
    z-index: 999; transition: transform 0.2s;
    user-select: none;
}
.chat-fab:hover { transform: scale(1.08); }
.chat-panel {
    position: fixed; bottom: 92px; right: 28px;
    width: 380px; height: 520px;
    background: #fff; border-radius: 12px;
    box-shadow: 0 8px 32px rgba(0,0,0,0.15);
    display: flex; flex-direction: column;
    z-index: 998; overflow: hidden;
    border: 1px solid #e4e7ed;
}
.chat-header {
    display: flex; align-items: center; gap: 6px;
    padding: 12px 16px;
    border-bottom: 1px solid #ebeef5;
    background: #f8f9fa;
    font-size: 14px; flex-shrink: 0;
}
.chat-messages {
    flex: 1; overflow-y: auto; padding: 12px 16px;
    background: #f5f7fa;
}
.chat-welcome {
    text-align: center; padding: 20px 4px;
    font-size: 13px; color: #606266; line-height: 1.8;
}
.chat-suggestions { margin-top: 12px; display: flex; flex-wrap: wrap; gap: 6px; justify-content: center; }
.suggestion-tag {
    display: inline-block; padding: 4px 12px;
    background: #ecf5ff; color: #409eff;
    border-radius: 14px; font-size: 12px;
    cursor: pointer; transition: background 0.15s;
}
.suggestion-tag:hover { background: #d9ecff; }
.chat-msg { margin-bottom: 10px; display: flex; }
.chat-msg-user { justify-content: flex-end; }
.chat-msg-ai { justify-content: flex-start; }
.chat-msg-content {
    max-width: 85%; padding: 8px 12px;
    border-radius: 8px; font-size: 13px; line-height: 1.6;
    white-space: pre-wrap; word-break: break-word;
}
.chat-msg-user .chat-msg-content {
    background: #409eff; color: #fff;
    border-bottom-right-radius: 2px;
}
.chat-msg-ai .chat-msg-content {
    background: #fff; color: #303133;
    border: 1px solid #e4e7ed;
    border-bottom-left-radius: 2px;
}
.chat-typing { color: #909399 !important; }
.chat-typing span { animation: dot-blink 1.4s infinite; }
.chat-typing span:nth-child(2) { animation-delay: 0.2s; }
.chat-typing span:nth-child(3) { animation-delay: 0.4s; }
@keyframes dot-blink { 0%,80%,100% { opacity: 0; } 40% { opacity: 1; } }
.chat-input-area {
    display: flex; align-items: center;
    padding: 10px 12px; border-top: 1px solid #ebeef5;
    background: #fff; flex-shrink: 0;
}
/* 面板滑入动画 */
.chat-slide-enter-active { transition: all 0.25s ease; }
.chat-slide-leave-active { transition: all 0.2s ease; }
.chat-slide-enter-from { opacity: 0; transform: translateY(20px) scale(0.95); }
.chat-slide-leave-to { opacity: 0; transform: translateY(10px) scale(0.97); }

/* ===== 杜邦分析 ===== */
.dupont-factor-card { text-align: center; }
.dupont-factor-card :deep(.el-card__body) { padding: 20px 16px; }
.dupont-factor-title { font-size: 13px; color: #909399; margin-bottom: 8px; }
.dupont-factor-value { font-size: 28px; font-weight: bold; color: #e6a23c; margin-bottom: 6px; }
.dupont-factor-desc { font-size: 11px; color: #c0c4cc; }
</style>
