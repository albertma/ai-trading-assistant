<template>
    <div class="narratives-page">
        <!-- 顶部信息条 -->
        <el-card shadow="hover" style="margin-bottom:16px;">
            <el-row :gutter="16" align="middle">
                <el-col :span="3">
                    <b style="font-size:16px;">🎯 叙事分析</b>
                </el-col>
                <el-col :span="4">
                    <el-date-picker
                        v-model="selectedDate"
                        type="date"
                        placeholder="选择日期"
                        :disabled-date="disabledDate"
                        format="YYYY-MM-DD"
                        value-format="YYYY-MM-DD"
                        @change="onDateChange"
                        style="width:100%" clearable />
                </el-col>
                <el-col :span="6">
                    <el-tag v-if="dataDate" type="info" effect="plain" size="large" style="margin-right:8px;">📅 {{ dataDate }}</el-tag>
                    <el-tag v-if="isCached" type="success" effect="plain" size="small">已保存</el-tag>
                    <el-tag v-else-if="!isCached && narratives.length" type="warning" effect="plain" size="small">新分析</el-tag>
                    <el-tag v-if="marketAvgChange != null" :type="marketAvgChange >= 0 ? 'danger' : 'success'" effect="dark" size="large" style="margin-left:4px;">
                        大盘 {{ marketAvgChange >= 0 ? '+' : '' }}{{ marketAvgChange }}%
                    </el-tag>
                </el-col>
                <el-col :span="5" style="text-align:center;">
                    <el-tag type="info" effect="plain" size="medium">发现 <b>{{ narratives.length }}</b> 个叙事主题</el-tag>
                    <el-tag v-if="prevContextDate" type="info" effect="plain" size="small" style="margin-left:4px;">📜 参考前{{ prevContextDays }}日</el-tag>
                </el-col>
                <el-col :span="6" style="text-align:right;">
                    <el-button type="warning" plain @click="refreshNarratives" :loading="narrativesLoading">⟳ AI重新分析</el-button>
                </el-col>
            </el-row>
        </el-card>

        <!-- 两个子菜单 Tab -->
        <el-card shadow="hover" style="margin-bottom:16px;">
            <el-tabs v-model="activeTab" @tab-change="onTabChange">
                <!-- ======== Tab 1: 按人物 ======== -->
                <el-tab-pane label="👤 按人物" name="by-person">
                    <el-row :gutter="12" style="margin-bottom:12px;">
                        <el-col :span="3">
                            <el-select v-model="personSummaryMarket" size="small" @change="loadPersonSummary">
                                <el-option label="全部市场" value="all" />
                                <el-option label="🇺🇸 美股" value="us" />
                                <el-option label="🇨🇳 A股" value="cn" />
                                <el-option label="₿ 加密" value="crypto" />
                            </el-select>
                        </el-col>
                        <el-col :span="5">
                            <el-button type="primary" size="small" @click="triggerFetchNews" :loading="fetchLoading" :disabled="!networkAvailable">📰 拉取新闻</el-button>
                            <el-button type="warning" size="small" @click="triggerDedup" style="margin-left:4px;">🔄 去重</el-button>
                            <el-tag v-if="networkAvailable === true" size="small" type="success" effect="plain" style="margin-left:4px;">网络正常</el-tag>
                            <el-tag v-else-if="networkAvailable === false" size="small" type="danger" effect="plain" style="margin-left:4px;">网络不可达</el-tag>
                        </el-col>
                    </el-row>

                    <div v-if="personSummaryLoading" style="text-align:center;padding:40px;color:#909399;"><el-icon class="is-loading"><Loading /></el-icon> 加载中...</div>
                    <div v-else-if="!personSummary.length" style="text-align:center;padding:40px;color:#909399;font-size:13px;">暂无数据，请先拉取新闻</div>

                    <template v-else>
                        <el-row :gutter="12">
                            <el-col v-for="p in personSummary" :key="p.person_id" :xs="24" :sm="12" :lg="8" style="margin-bottom:12px;">
                                <el-card shadow="hover" :style="{ borderTop: '3px solid ' + marketColor(p.market), cursor:'pointer' }" @click="showPersonDetail(p)">
                                    <!-- 人物头部 -->
                                    <div style="display:flex;justify-content:space-between;align-items:flex-start;">
                                        <div>
                                            <div style="display:flex;align-items:center;gap:4px;">
                                                <b>{{ p.person_name }}</b>
                                                <el-tag size="small" :type="p.market === 'us' ? 'primary' : (p.market === 'cn' ? 'warning' : 'success')" effect="plain">
                                                    {{ {us:'🇺🇸',cn:'🇨🇳',crypto:'₿'}[p.market] || p.market }}
                                                </el-tag>
                                            </div>
                                            <div style="font-size:11px;color:#909399;margin-top:2px;">{{ p.person_title }}</div>
                                        </div>
                                        <el-tag size="small" type="info" effect="plain">{{ p.statement_count }} 条</el-tag>
                                    </div>
                                    <!-- 情绪 -->
                                    <div style="margin-top:10px;display:flex;gap:6px;font-size:12px;">
                                        <el-tag v-if="p.sentiment_distribution.positive" size="small" type="success" effect="dark">📈 {{ p.sentiment_distribution.positive }}</el-tag>
                                        <el-tag v-if="p.sentiment_distribution.negative" size="small" type="danger" effect="dark">📉 {{ p.sentiment_distribution.negative }}</el-tag>
                                        <el-tag v-if="p.sentiment_distribution.neutral" size="small" type="info" effect="plain">📌 {{ p.sentiment_distribution.neutral }}</el-tag>
                                    </div>
                                    <!-- Ticker & 主题 -->
                                    <div v-if="p.top_tickers?.length" style="margin-top:8px;">
                                        <el-tag v-for="t in p.top_tickers" :key="t" size="small" type="success" effect="dark" style="margin-right:2px;">{{ t }}</el-tag>
                                    </div>
                                    <div v-if="p.top_topics?.length" style="margin-top:6px;">
                                        <el-tag v-for="t in p.top_topics" :key="t" size="small" type="info" effect="plain" style="margin-right:2px;">{{ t }}</el-tag>
                                    </div>
                                </el-card>
                            </el-col>
                        </el-row>
                    </template>
                </el-tab-pane>

                <!-- ======== Tab 2: 按言论 ======== -->
                <el-tab-pane label="💬 按言论" name="by-statement">
                    <el-row :gutter="12" style="margin-bottom:12px;">
                        <el-col :span="3">
                            <el-select v-model="statementNarrativeMarket" size="small" @change="loadStatementNarratives">
                                <el-option label="全部市场" value="all" />
                                <el-option label="🇺🇸 美股" value="us" />
                                <el-option label="🇨🇳 A股" value="cn" />
                                <el-option label="₿ 加密" value="crypto" />
                            </el-select>
                        </el-col>
                        <el-col :span="2"><el-tag type="info" effect="plain" size="small">{{ statementNarratives.length }} 个主题</el-tag></el-col>
                        <el-col :span="6">
                            <el-button type="primary" size="small" @click="triggerFetchNews" :loading="fetchLoading" :disabled="!networkAvailable">📰 拉取新闻</el-button>
                        </el-col>
                    </el-row>

                    <div v-if="statementNarrativesLoading" style="text-align:center;padding:40px;color:#909399;"><el-icon class="is-loading"><Loading /></el-icon> 加载中...</div>
                    <div v-else-if="!statementNarratives.length" style="text-align:center;padding:40px;color:#909399;font-size:13px;">暂无数据，请先拉取新闻</div>

                    <template v-else>
                        <el-row :gutter="12">
                            <el-col v-for="(topic, ti) in statementNarratives" :key="ti" :xs="24" :sm="12" style="margin-bottom:12px;">
                                <el-card shadow="hover">
                                    <div style="display:flex;justify-content:space-between;align-items:center;">
                                        <b style="font-size:15px;">{{ topic.topic }}</b>
                                        <el-tag size="small" type="info" effect="plain">{{ topic.statement_count }} 条</el-tag>
                                    </div>
                                    <!-- 情绪 -->
                                    <div style="margin-top:8px;display:flex;gap:4px;">
                                        <el-tag v-if="topic.sentiment_ratio.positive" size="small" type="success" effect="dark">📈 {{ topic.sentiment_ratio.positive }}</el-tag>
                                        <el-tag v-if="topic.sentiment_ratio.negative" size="small" type="danger" effect="dark">📉 {{ topic.sentiment_ratio.negative }}</el-tag>
                                        <el-tag v-if="topic.sentiment_ratio.neutral" size="small" type="info" effect="plain">📌 {{ topic.sentiment_ratio.neutral }}</el-tag>
                                    </div>
                                    <!-- 相关资产 -->
                                    <div v-if="topic.tickers?.length" style="margin-top:6px;">
                                        <span style="font-size:11px;color:#909399;">资产: </span>
                                        <el-tag v-for="t in topic.tickers" :key="t" size="small" type="success" effect="dark" style="margin-right:2px;">{{ t }}</el-tag>
                                    </div>
                                    <!-- 人物 -->
                                    <div v-if="topic.people?.length" style="margin-top:4px;">
                                        <span style="font-size:11px;color:#909399;">人物: </span>
                                        <el-tag v-for="p in topic.people" :key="p" size="small" type="warning" effect="plain" style="margin-right:2px;">{{ p }}</el-tag>
                                    </div>
                                    <!-- 最新言论 -->
                                    <div v-if="topic.latest_statements?.length" style="margin-top:10px;padding-top:8px;border-top:1px solid #ebeef5;">
                                        <div style="font-size:11px;color:#909399;margin-bottom:4px;">最新言论:</div>
                                        <div v-for="s in topic.latest_statements.slice(0,3)" :key="s.id" style="font-size:12px;color:#606266;line-height:1.5;margin-bottom:4px;padding-left:8px;border-left:2px solid #dcdfe6;">
                                            <div style="display:flex;align-items:center;gap:4px;">
                                                <b>{{ s.person_name }}</b>
                                                <span style="font-size:11px;color:#909399;">{{ s.statement_date }}</span>
                                                <span v-if="s.sentiment === 'positive'" style="color:#67c23a;">📈</span>
                                                <span v-else-if="s.sentiment === 'negative'" style="color:#f56c6c;">📉</span>
                                            </div>
                                            <div style="margin-top:2px;">{{ s.statement }}</div>
                                        </div>
                                    </div>
                                </el-card>
                            </el-col>
                        </el-row>
                    </template>
                </el-tab-pane>

                <!-- ======== Tab 3: 深度推演 ======== -->
                <el-tab-pane label="🧠 深度推演" name="deep-analysis">
                    <div style="margin-bottom:12px;display:flex;gap:8px;align-items:center;">
                        <el-button type="warning" @click="generateDeepAnalysis" :loading="deepAnalysisLoading">🧠 AI深度推演</el-button>
                        <el-tag v-if="deepAnalysisCached" type="success" effect="plain" size="small">已缓存</el-tag>
                        <span v-if="deepAnalysisError" style="color:#f56c6c;font-size:12px;">{{ deepAnalysisError }}</span>
                    </div>

                    <div v-if="deepAnalysisLoading" style="text-align:center;padding:40px;color:#909399;">
                        <el-icon class="is-loading" :size="32"><Loading /></el-icon>
                        <p style="margin-top:12px;">AI正在跨叙事推演分析...</p>
                    </div>
                    <div v-else-if="!deepAnalysis" style="text-align:center;padding:40px;color:#909399;font-size:13px;">
                        点击「AI深度推演」生成跨叙事交叉分析
                    </div>

                    <template v-else>
                        <!-- 核心矛盾 -->
                        <el-card shadow="hover" style="margin-bottom:16px;border-left:4px solid #e6a23c;">
                            <div style="display:flex;align-items:center;gap:8px;margin-bottom:8px;">
                                <span style="font-size:20px;">⚡</span>
                                <b style="font-size:16px;">{{ deepAnalysis.core_contradiction?.title }}</b>
                                <el-tag v-if="deepAnalysis.core_contradiction?.severity === 'high'" size="small" type="danger" effect="dark">高风险</el-tag>
                                <el-tag v-else-if="deepAnalysis.core_contradiction?.severity === 'medium'" size="small" type="warning" effect="dark">中风险</el-tag>
                                <el-tag v-else size="small" type="info" effect="dark">低风险</el-tag>
                            </div>
                            <p style="font-size:13px;color:#555;line-height:1.7;">{{ deepAnalysis.core_contradiction?.analysis }}</p>
                            <div v-if="deepAnalysis.core_contradiction?.key_numbers?.length" style="margin-top:8px;display:flex;gap:8px;flex-wrap:wrap;">
                                <el-tag v-for="n in deepAnalysis.core_contradiction.key_numbers" :key="n" size="small" type="warning" effect="plain">{{ n }}</el-tag>
                            </div>
                        </el-card>

                        <!-- 板块深度拆解 -->
                        <div style="font-size:14px;font-weight:bold;margin-bottom:10px;">🔍 板块深度拆解</div>
                        <el-row :gutter="12">
                            <el-col :xs="24" :sm="12" v-for="(sd, i) in deepAnalysis.sector_deep_dives" :key="i" style="margin-bottom:12px;">
                                <el-card shadow="hover" :style="{ borderTop: '3px solid ' + (sd.verdict === 'bullish' ? '#67c23a' : sd.verdict === 'bearish' ? '#f56c6c' : '#909399') }">
                                    <div style="display:flex;justify-content:space-between;align-items:center;margin-bottom:6px;">
                                        <b style="font-size:14px;">{{ sd.name }}</b>
                                        <el-tag size="small" :type="sd.verdict === 'bullish' ? 'success' : sd.verdict === 'bearish' ? 'danger' : 'info'" effect="dark">
                                            {{ sd.verdict === 'bullish' ? '📈 看多' : sd.verdict === 'bearish' ? '📉 看空' : '➡️ 中性' }}
                                        </el-tag>
                                    </div>
                                    <p style="font-size:12px;color:#555;line-height:1.6;">{{ sd.insight }}</p>
                                    <div v-if="sd.key_metrics?.length" style="margin-top:6px;">
                                        <el-tag v-for="m in sd.key_metrics" :key="m" size="small" type="info" effect="plain" style="margin-right:4px;">{{ m }}</el-tag>
                                    </div>
                                </el-card>
                            </el-col>
                        </el-row>

                        <!-- 关键质疑 -->
                        <div style="font-size:14px;font-weight:bold;margin:16px 0 10px;">❓ 关键质疑（对立视角）</div>
                        <el-row :gutter="12">
                            <el-col :xs="24" :sm="12" v-for="(cq, i) in deepAnalysis.critical_questions" :key="i" style="margin-bottom:12px;">
                                <el-card shadow="hover" style="border-left:3px solid #f56c6c;">
                                    <div style="display:flex;align-items:center;gap:6px;margin-bottom:6px;">
                                        <b style="font-size:13px;">{{ cq.question }}</b>
                                        <el-tag size="small" :type="cq.risk_level === 'high' ? 'danger' : cq.risk_level === 'medium' ? 'warning' : 'info'" effect="dark">
                                            {{ cq.risk_level === 'high' ? '高风险' : cq.risk_level === 'medium' ? '中风险' : '低风险' }}
                                        </el-tag>
                                    </div>
                                    <p style="font-size:12px;color:#555;line-height:1.6;">{{ cq.counter_analysis }}</p>
                                </el-card>
                            </el-col>
                        </el-row>

                        <!-- 观察清单 -->
                        <div style="font-size:14px;font-weight:bold;margin:16px 0 10px;">👁️ 后续观察清单</div>
                        <el-table :data="deepAnalysis.watchlist || []" border size="small" style="width:100%;margin-bottom:16px;">
                            <el-table-column label="信号" prop="signal" min-width="150" />
                            <el-table-column label="观察什么" prop="what_to_watch" min-width="200" />
                            <el-table-column label="如果成立意味着" prop="implication" min-width="200" />
                        </el-table>

                        <!-- 最终结论 -->
                        <el-card shadow="hover" style="border-left:4px solid #409eff;">
                            <div style="display:flex;align-items:center;gap:8px;margin-bottom:6px;"><span style="font-size:18px;">🎯</span><b>最终结论</b></div>
                            <p style="font-size:13px;color:#555;line-height:1.7;">{{ deepAnalysis.bottom_line }}</p>
                        </el-card>
                    </template>
                </el-tab-pane>
            </el-tabs>
        </el-card>

        <!-- 叙事网格 -->
        <div v-if="narrativesLoading && !narratives.length" style="text-align:center;padding:60px;">
            <el-icon class="is-loading" :size="32"><Loading /></el-icon>
            <p style="color:#909399;margin-top:12px;">AI正在分析市场数据，发现叙事主题...</p>
        </div>
        <div v-else-if="narratives.length === 0" style="text-align:center;padding:60px;"><el-empty :description="noDataMsg || '暂无数据'" /></div>
        <template v-else>
            <div style="margin-bottom:12px;display:flex;gap:8px;flex-wrap:wrap;align-items:center;">
                <el-tag :type="stageFilter === '' ? 'primary' : 'info'" effect="plain" style="cursor:pointer;" @click="stageFilter = ''">全部 {{ narratives.length }}</el-tag>
                <el-tag v-for="(count, stage) in stageCounts" :key="stage"
                    :color="lifecycleColor(stage)" effect="dark" style="cursor:pointer;color:#fff;border:0;"
                    :style="{ opacity: stageFilter === '' || stageFilter === stage ? 1 : 0.5 }"
                    @click="stageFilter = stageFilter === stage ? '' : stage">
                    {{ stage }} {{ count }}
                </el-tag>
            </div>
            <el-row :gutter="12">
                <el-col :xs="24" :sm="12" :lg="8" v-for="(n, ni) in filteredNarratives" :key="ni" style="margin-bottom:12px;">
                    <el-card shadow="hover" style="height:100%;" :style="{ borderTop: '4px solid ' + lifecycleColor(n.lifecycle_stage) }">
                        <div style="display:flex;justify-content:space-between;align-items:flex-start;margin-bottom:10px;">
                            <div style="flex:1;">
                                <div style="display:flex;align-items:center;gap:6px;margin-bottom:6px;">
                                    <b style="font-size:16px;">{{ n.name }}</b>
                                    <el-tag size="small" :color="lifecycleColor(n.lifecycle_stage)" effect="dark" style="color:#fff;border:0;">{{ n.lifecycle_stage }}</el-tag>
                                    <el-tag size="small" type="info" effect="plain">{{ n.category }}</el-tag>
                                </div>
                            </div>
                        </div>
                        <p style="font-size:13px;color:#b0b0b0;line-height:1.6;margin-bottom:8px;">{{ n.description }}</p>
                        <p v-if="n.trigger_event" style="font-size:11px;color:#909399;margin-bottom:10px;line-height:1.5;">💡 <b>触发：</b>{{ n.trigger_event }}</p>
                        <div style="margin-bottom:10px;">
                            <div style="display:flex;justify-content:space-between;font-size:11px;color:#909399;margin-bottom:2px;">
                                <span>生命周期</span><span :style="{ color: lifecycleColor(n.lifecycle_stage) }">{{ n.lifecycle_score }}%</span>
                            </div>
                            <el-progress :percentage="n.lifecycle_score" :stroke-width="8" :color="lifecycleColor(n.lifecycle_stage)" :format="() => ''" />
                        </div>
                        <div style="margin-bottom:10px;">
                            <div style="display:flex;justify-content:space-between;font-size:11px;color:#909399;margin-bottom:2px;">
                                <span>被证实程度</span>
                                <span :style="{ color: confirmColor(n.confirmation_score) }">{{ n.confirmation_score }}% {{ confirmArrow(n.confirmation_trend) }}</span>
                            </div>
                            <el-progress :percentage="n.confirmation_score" :stroke-width="8" :color="confirmColor(n.confirmation_score)" :format="() => ''" />
                        </div>
                        <el-collapse v-model="openPanels" style="margin-bottom:8px;">
                            <el-collapse-item :name="'ev_'+ni" style="font-size:12px;">
                                <template #title>📋 证据 <span style="color:#67c23a;">支持{{ n.evidence_supporting?.length || 0 }}</span>/<span style="color:#f56c6c;">反对{{ n.evidence_contradicting?.length || 0 }}</span></template>
                                <div v-if="n.evidence_supporting?.length"><div style="font-size:11px;color:#67c23a;">✅ 支持</div><ul style="margin:0;padding-left:16px;"><li v-for="ev in n.evidence_supporting" :key="ev" style="font-size:11px;color:#b0b0b0;">{{ ev }}</li></ul></div>
                                <div v-if="n.evidence_contradicting?.length"><div style="font-size:11px;color:#f56c6c;">⛔ 反对</div><ul style="margin:0;padding-left:16px;"><li v-for="ev in n.evidence_contradicting" :key="ev" style="font-size:11px;color:#b0b0b0;">{{ ev }}</li></ul></div>
                            </el-collapse-item>
                            <el-collapse-item :name="'bias_'+ni" style="font-size:12px;">
                                <template #title>🧠 认知偏差（{{ n.biases_detail?.length || 0 }}）</template>
                                <div v-for="b in (n.biases_detail || [])" :key="b.name" style="margin-bottom:6px;font-size:11px;">
                                    <el-tag size="small" type="warning" effect="plain" style="margin-right:4px;">{{ b.name }}</el-tag><span style="color:#909399;">{{ b.desc }}</span>
                                </div>
                            </el-collapse-item>
                        </el-collapse>
                        <div style="display:flex;flex-wrap:wrap;gap:4px;margin-top:8px;padding-top:8px;border-top:1px solid #ebeef5;">
                            <el-tag v-for="s in (n.related_sectors || [])" :key="s" size="small" type="info" effect="plain">{{ s }}</el-tag>
                            <el-tag v-for="s in (n.related_stocks || [])" :key="s" size="small" type="success" effect="plain">{{ s }}</el-tag>
                            <el-tag v-for="p in (n.related_people || [])" :key="p" size="small" type="warning" effect="dark" style="color:#fff;border:0;">👤 {{ p }}</el-tag>
                        </div>
                    </el-card>
                </el-col>
            </el-row>
        </template>

        <!-- 人物详情对话框 -->
        <el-dialog v-model="detailDialogVisible" :title="'👤 ' + (detailPerson?.person_name || '')" width="700px" :close-on-click-modal="false">
            <div v-if="detailLoading" style="text-align:center;padding:30px;color:#909399;"><el-icon class="is-loading"><Loading /></el-icon> 加载中...</div>
            <template v-else-if="detailStatements.length">
                <el-timeline style="padding-left:0;">
                    <el-timeline-item
                        v-for="s in detailStatements" :key="s.id"
                        :timestamp="s.statement_date"
                        placement="top"
                        :color="s.market === 'us' ? '#409eff' : (s.market === 'cn' ? '#e6a23c' : '#67c23a')"
                    >
                        <div style="display:flex;align-items:center;gap:4px;margin-bottom:2px;">
                            <el-tag v-if="s.sentiment === 'positive'" size="small" type="success" effect="dark">看多</el-tag>
                            <el-tag v-else-if="s.sentiment === 'negative'" size="small" type="danger" effect="dark">看空</el-tag>
                            <el-tag v-else size="small" type="info" effect="plain">中性</el-tag>
                            <span style="font-size:11px;color:#909399;">{{ s.source }}</span>
                        </div>
                        <p style="font-size:13px;color:#555;margin:4px 0;line-height:1.5;">{{ s.statement }}</p>
                        <div style="display:flex;gap:8px;flex-wrap:wrap;font-size:11px;">
                            <span v-if="s.related_tickers" style="color:#909399;">📎 {{ s.related_tickers }}</span>
                            <a v-if="s.source_url" :href="s.source_url" target="_blank" rel="noopener" style="color:#409eff;text-decoration:none;" @click.stop>🔗 原文链接</a>
                        </div>
                    </el-timeline-item>
                </el-timeline>
            </template>
            <div v-else style="text-align:center;padding:30px;color:#909399;">暂无详细言论</div>
        </el-dialog>
    </div>
</template>

<script setup>
import { ref, computed, onMounted } from 'vue'
import { ElMessage } from 'element-plus'
import { getMarketNarratives, getNarrativeDates, getPersonStatements, getPersonSummary, getStatementNarratives, fetchNews, checkNetwork, dedupStatements, getDeepNarrativeAnalysis } from '../api/index.js'

const narratives = ref([])
const dataDate = ref('')
const marketAvgChange = ref(null)
const narrativesLoading = ref(false)
const stageFilter = ref('')
const openPanels = ref([])
const selectedDate = ref(null)
const availableDates = ref([])
const isCached = ref(true)
const noDataMsg = ref('')
const prevContextDate = ref('')
const prevContextDays = ref(0)

// 深度推演
const deepAnalysis = ref(null)
const deepAnalysisLoading = ref(false)
const deepAnalysisCached = ref(false)
const deepAnalysisError = ref('')

const activeTab = ref('by-person')
const fetchLoading = ref(false)
const networkAvailable = ref(null)

// Tab1: 按人物
const personSummary = ref([])
const personSummaryLoading = ref(false)
const personSummaryMarket = ref('all')

// Tab2: 按言论（叙事主题分组）
const statementNarratives = ref([])
const statementNarrativesLoading = ref(false)
const statementNarrativeMarket = ref('all')

// 详情对话框
const detailDialogVisible = ref(false)
const detailPerson = ref(null)
const detailStatements = ref([])
const detailLoading = ref(false)

const stageCounts = computed(() => {
    const counts = {}
    for (const n of narratives.value) counts[n.lifecycle_stage] = (counts[n.lifecycle_stage] || 0) + 1
    return counts
})

const filteredNarratives = computed(() => !stageFilter.value ? narratives.value : narratives.value.filter(n => n.lifecycle_stage === stageFilter.value))
const dateSet = computed(() => new Set(availableDates.value))

function disabledDate(time) {
    const d = time.getFullYear()+'-'+String(time.getMonth()+1).padStart(2,'0')+'-'+String(time.getDate()).padStart(2,'0')
    return !dateSet.value.has(d)
}
function marketColor(m) { return {us:'#409eff',cn:'#e6a23c',crypto:'#67c23a'}[m]||'#909399' }

async function loadNarratives(forceRefresh = false) {
    narrativesLoading.value = true; noDataMsg.value = ''
    try {
        const { data } = await getMarketNarratives(forceRefresh, selectedDate.value)
        narratives.value = data.narratives || []; dataDate.value = data.date || ''
        marketAvgChange.value = data.market_avg_change; isCached.value = data.cached !== false
        noDataMsg.value = data.message || ''
    } catch(e) { console.error(e); noDataMsg.value='加载失败' }
    finally { narrativesLoading.value = false }
}

async function loadPersonSummary() {
    personSummaryLoading.value = true
    try { const { data } = await getPersonSummary(personSummaryMarket.value, 7); personSummary.value = data.summary || [] }
    catch(e) { console.error(e) }
    finally { personSummaryLoading.value = false }
}

async function loadStatementNarratives() {
    statementNarrativesLoading.value = true
    try { const { data } = await getStatementNarratives(statementNarrativeMarket.value, 7); statementNarratives.value = data.narratives || [] }
    catch(e) { console.error(e) }
    finally { statementNarrativesLoading.value = false }
}

async function showPersonDetail(p) {
    detailPerson.value = p; detailDialogVisible.value = true; detailLoading.value = true; detailStatements.value = []
    try {
        const { data } = await getPersonStatements('all', 30, 50, p.person_id)
        detailStatements.value = data.statements || []
    } catch(e) { console.error(e) }
    finally { detailLoading.value = false }
}

async function triggerFetchNews() {
    fetchLoading.value = true
    try {
        const { data } = await fetchNews()
        ElMessage.success(data.status === 'error' ? `抓取失败: ${data.message}` : `获取${data.total_fetched}条, 入库${data.total_saved}条`)
        await Promise.all([loadPersonSummary(), loadStatementNarratives()])
    } catch(e) { ElMessage.error('拉取失败: '+(e.message||'未知错误')) }
    finally { fetchLoading.value = false }
}

async function triggerDedup() {
    try {
        const { data } = await dedupStatements()
        ElMessage.success(`去重完成: 删除${data.deleted}条, 保留${data.kept}条`)
        await Promise.all([loadPersonSummary(), loadStatementNarratives()])
    } catch(e) { ElMessage.error('去重失败: '+e.message) }
}

function onTabChange(tab) {
    if (tab === 'by-person' && !personSummary.value.length) loadPersonSummary()
    if (tab === 'by-statement' && !statementNarratives.value.length) loadStatementNarratives()
}

function onDateChange(val) { selectedDate.value = val; loadNarratives() }
function refreshNarratives() { loadNarratives(true) }

async function generateDeepAnalysis() {
    deepAnalysisLoading.value = true
    deepAnalysisError.value = ''
    try {
        const { data } = await getDeepNarrativeAnalysis(selectedDate.value)
        if (data.status === 'ok') {
            deepAnalysis.value = data.analysis
            deepAnalysisCached.value = data.cached
        } else {
            deepAnalysisError.value = data.message || '生成失败'
            deepAnalysis.value = null
        }
    } catch (e) {
        deepAnalysisError.value = '请求失败: ' + (e.response?.data?.detail || e.message)
        deepAnalysis.value = null
    } finally {
        deepAnalysisLoading.value = false
    }
}
function lifecycleColor(s) { return {萌芽:'#909399',发酵:'#409eff',高潮:'#e6a23c',退潮:'#f56c6c',证伪:'#909399'}[s]||'#909399' }
function confirmColor(s) { return s>=70?'#67c23a':s>=40?'#e6a23c':'#f56c6c' }
function confirmArrow(t) { return {confirming:'📈',disproving:'📉',stable:'➡️'}[t]||'' }

onMounted(async () => {
    try { const { data } = await getNarrativeDates(); availableDates.value = data.dates || []; if (availableDates.value.length) selectedDate.value = availableDates.value[0] } catch(e) { console.error(e) }
    await loadNarratives(); await loadPersonSummary(); await loadStatementNarratives()
    try { const { data } = await checkNetwork(); networkAvailable.value = data.available } catch(e) { networkAvailable.value = false }
})
</script>

<style scoped>
.narratives-page { max-width:1400px; margin:0 auto; }
</style>
