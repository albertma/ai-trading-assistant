<template>
    <div class="dashboard">
        <!-- 构建版本号 -->
        <div style="position:fixed;right:12px;top:52px;z-index:999;font-size:10px;color:#c0c4cc;text-align:right;line-height:1.4;">
            <div>v{{ buildVersion.version || '-' }}</div>
            <div>{{ (buildVersion.build_time || '').slice(11,16) }}</div>
        </div>

        <!-- 日期选择条 -->
        <el-card shadow="hover" style="margin-bottom: 16px;">
            <el-row :gutter="16" align="middle">
                <el-col :span="4">
                    <el-date-picker
                        v-model="selectedDate"
                        type="date"
                        placeholder="选择日期"
                        :disabled-date="disabledDate"
                        format="YYYY-MM-DD"
                        value-format="YYYY-MM-DD"
                        @change="onDateChange"
                        style="width:100%"
                    />
                </el-col>
                <el-col :span="2">
                    <el-button @click="toPrevDay" :disabled="!prevDate" size="default">‹ 前一天</el-button>
                </el-col>
                <el-col :span="2">
                    <el-button @click="toNextDay" :disabled="!nextDate" size="default">后一天 ›</el-button>
                </el-col>
                <el-col :span="4">
                    <el-tag v-if="dataDate" type="info" effect="plain" size="large">
                        📅 {{ dataDate }}
                    </el-tag>
                </el-col>
                <el-col :span="2" v-if="sessionsAvailable.length > 1">
                    <el-radio-group v-model="dataSession" size="small" @change="onSessionChange">
                        <el-radio-button value="noon">午市</el-radio-button>
                        <el-radio-button value="close">收盘</el-radio-button>
                    </el-radio-group>
                </el-col>
                <el-col :span="2" v-else>
                    <el-tag v-if="dataDate" :type="dataSession === 'noon' ? 'warning' : 'success'" size="small">
                        {{ dataSession === 'noon' ? '🌤 午市' : '🌙 收盘' }}
                    </el-tag>
                </el-col>
                <el-col :span="3" style="text-align:center;">
                    <el-button v-if="dataDate" size="small" type="warning" plain
                        @click="handleRefreshMarket" :loading="refreshing" :disabled="refreshing">
                        {{ refreshing ? '下载中...' : '🔄 重新下载' }}
                    </el-button>
                </el-col>
                <el-col :span="5" style="text-align:right;">
                    <el-tag v-if="dataDate" :type="marketSentiment.type" effect="dark" size="large">
                        {{ marketSentiment.text }}
                    </el-tag>
                </el-col>
            </el-row>
        </el-card>

        <!-- 每日操盘笔记 -->
        <el-card v-if="dailyNote" shadow="hover" style="margin-bottom:16px;"
            :style="{ borderLeft: '4px solid #e6a23c', background: '#fdf6ec' }">
            <template #header>
                <div style="display:flex;justify-content:space-between;align-items:center;">
                    <b>📝 操盘笔记 ({{ dataDate || '今日' }})</b>
                    <el-button size="small" type="warning" plain @click="editingNote = !editingNote">
                        {{ editingNote ? '完成' : '编辑' }}
                    </el-button>
                </div>
            </template>
            <div v-if="!editingNote" style="font-size:13px;color:#856404;line-height:1.7;white-space:pre-wrap;">{{ dailyNote }}</div>
            <el-input v-else v-model="dailyNote" type="textarea" :rows="3" placeholder="输入操盘笔记..." />
        </el-card>

        <!-- 沪深300 vs 中证500 双轴对比图 -->
        <el-card v-if="indexData.hs300.length" shadow="hover" style="margin-top:16px;">
            <template #header>
                <div style="display:flex;justify-content:space-between;align-items:center;">
                    <b>📈 沪深300 vs 中证500</b>
                    <el-radio-group v-model="indexDays" size="small" @change="loadIndexHistory">
                        <el-radio-button value="30">30天</el-radio-button>
                        <el-radio-button value="60">60天</el-radio-button>
                        <el-radio-button value="120">120天</el-radio-button>
                        <el-radio-button value="730">2年</el-radio-button>
                    </el-radio-group>
                </div>
            </template>
            <div ref="indexChartRef" style="width:100%;height:380px;"></div>
        </el-card>

        <!-- 市场状态卡片 -->
        <el-row v-if="!noData" :gutter="16">
            <el-col :span="6" v-for="card in statCards" :key="card.label">
                <el-card shadow="hover" class="stat-card" :class="card.cls">
                    <div class="stat-value" :style="{ color: card.color }">{{ card.value }}</div>
                    <div class="stat-label">{{ card.label }}</div>
                </el-card>
            </el-col>
        </el-row>

        <!-- 市场情绪周期 -->
        <el-card v-if="!noData && cycleRecords.length" shadow="hover" style="margin-top:16px;margin-bottom:16px;">
            <template #header>
                <div style="display:flex;justify-content:space-between;align-items:center;">
                    <b>📊 市场情绪周期</b>
                    <div style="display:flex;align-items:center;gap:8px;">
                        <el-tag v-if="currentCycleLabel" :type="cycleTagType" size="large" effect="dark">
                            {{ currentCycleLabel }}
                        </el-tag>
                        <el-button size="small" text @click="cycleCollapsed = !cycleCollapsed">
                            {{ cycleCollapsed ? '展开分析' : '收起' }}
                        </el-button>
                    </div>
                </div>
            </template>
            <template v-if="!cycleCollapsed">
                <!-- 周期时间线 -->
                <div style="display:flex;gap:4px;margin-bottom:16px;overflow-x:auto;padding:8px 0;">
                    <div v-for="(r, i) in cycleRecords" :key="r.date"
                        style="flex:1;min-width:90px;text-align:center;padding:8px 6px;border-radius:8px;border:1px solid #334;position:relative;"
                        :style="{ background: cycleBgColor(r.stage) }">
                        <div style="font-size:11px;color:#909399;">{{ r.date.slice(5) }}</div>
                        <div style="font-size:13px;font-weight:bold;margin:4px 0;">{{ r.stage_label }}</div>
                        <div style="font-size:11px;">
                            <span :style="{color: r.avg_change_pct >= 0 ? '#f56c6c' : '#67c23a'}">{{ r.avg_change_pct >= 0 ? '+' : '' }}{{ r.avg_change_pct }}%</span>
                        </div>
                        <div style="font-size:10px;color:#909399;">↑{{ r.up }}/↓{{ r.down }}</div>
                        <div v-if="i < cycleRecords.length - 1" style="position:absolute;right:-6px;top:50%;transform:translateY(-50%);color:#555;font-size:14px;">→</div>
                    </div>
                </div>
                <!-- 详细数据表 -->
                <el-table :data="cycleRecords" size="small" stripe style="width:100%;margin-bottom:12px;">
                    <el-table-column label="日期" width="80">
                        <template #default="{ row }">{{ row.date.slice(5) }}</template>
                    </el-table-column>
                    <el-table-column label="周期阶段" width="110">
                        <template #default="{ row }">
                            <el-tag :type="cycleTagTypeByStage(row.stage)" size="small">{{ row.stage_label }}</el-tag>
                        </template>
                    </el-table-column>
                    <el-table-column label="涨跌比" width="70">
                        <template #default="{ row }">{{ row.ratio }}</template>
                    </el-table-column>
                    <el-table-column label="均涨幅" width="80">
                        <template #default="{ row }">
                            <span :style="{color: row.avg_change_pct >= 0 ? '#f56c6c' : '#67c23a'}">{{ row.avg_change_pct >= 0 ? '+' : '' }}{{ row.avg_change_pct }}%</span>
                        </template>
                    </el-table-column>
                    <el-table-column label="↑上涨" width="60">
                        <template #default="{ row }">{{ row.up }}</template>
                    </el-table-column>
                    <el-table-column label="↓下跌" width="60">
                        <template #default="{ row }">{{ row.down }}</template>
                    </el-table-column>
                    <el-table-column label="涨停" width="60">
                        <template #default="{ row }">{{ row.limit_up }}</template>
                    </el-table-column>
                    <el-table-column label="跌停" width="60">
                        <template #default="{ row }">{{ row.limit_down }}</template>
                    </el-table-column>
                </el-table>
                <!-- 趋势判断 -->
                <div v-if="cycleAssessment.outlook" style="padding:10px 14px;border-radius:8px;border:1px solid #334;font-size:13px;line-height:1.6;"
                    :style="{ background: cycleAssessmentBg }">
                    <div style="margin-bottom:4px;"><b>🔮 趋势判断</b></div>
                    <div>涨跌比趋势：<b>{{ cycleTrendLabel(cycleAssessment.ratio_trend) }}</b> · 均涨幅趋势：<b>{{ cycleTrendLabel(cycleAssessment.avg_trend) }}</b> · 涨停数趋势：<b>{{ cycleTrendLabel(cycleAssessment.limit_trend) }}</b></div>
                    <div style="margin-top:4px;">操作策略：<b>{{ cycleOutlookText }}</b></div>
                </div>
            </template>
        </el-card>

        <template v-if="!noData">
            <el-row :gutter="16" style="margin-top: 16px;">
                <el-col :span="12">
                    <el-card shadow="hover">
                        <template #header><b>📈 涨幅TOP10</b></template>
                        <el-table :data="gainers" size="small" stripe style="width:100%">
                            <el-table-column label="名称" min-width="100">
                                <template #default="{ row }">
                                    <router-link :to="`/analysis?code=${row.code}`" style="color:#409eff;text-decoration:none;">{{ row.name }}</router-link>
                                </template>
                            </el-table-column>
                            <el-table-column label="行业" min-width="100">
                                <template #default="{ row }">
                                    <el-tag size="mini" effect="plain">{{ row.sector || '--' }}</el-tag>
                                </template>
                            </el-table-column>
                            <el-table-column prop="change_pct" label="涨幅" width="90">
                                <template #default="{ row }">
                                    <span :style="{ color: (row.change_pct||0) >= 0 ? '#f56c6c' : '#67c23a' }">
                                        {{ (row.change_pct||0).toFixed(2) }}%
                                    </span>
                                </template>
                            </el-table-column>
                        </el-table>
                    </el-card>
                </el-col>
                <el-col :span="12">
                    <el-card shadow="hover">
                        <template #header><b>📉 跌幅TOP10</b></template>
                        <el-table :data="losers" size="small" stripe style="width:100%">
                            <el-table-column label="名称" min-width="100">
                                <template #default="{ row }">
                                    <router-link :to="`/analysis?code=${row.code}`" style="color:#409eff;text-decoration:none;">{{ row.name }}</router-link>
                                </template>
                            </el-table-column>
                            <el-table-column label="行业" min-width="100">
                                <template #default="{ row }">
                                    <el-tag size="mini" effect="plain">{{ row.sector || '--' }}</el-tag>
                                </template>
                            </el-table-column>
                            <el-table-column prop="change_pct" label="涨幅" width="90">
                                <template #default="{ row }">
                                    <span :style="{ color: (row.change_pct||0) >= 0 ? '#f56c6c' : '#67c23a' }">
                                        {{ (row.change_pct||0).toFixed(2) }}%
                                    </span>
                                </template>
                            </el-table-column>
                        </el-table>
                    </el-card>
                </el-col>
            </el-row>

            <el-row :gutter="16" style="margin-top: 16px;">
                <el-col :span="12">
                    <el-card shadow="hover">
                        <template #header><b>🔥 热门板块 TOP10</b></template>
                        <el-table :data="hotSectors" size="small" stripe style="width:100%">
                            <el-table-column type="index" label="#" width="50" />
                            <el-table-column prop="name" label="板块" min-width="140" />
                            <el-table-column prop="avg_change" label="平均涨幅" width="100">
                                <template #default="{ row }">
                                    <span :style="{ color: row.avg_change >= 0 ? '#f56c6c' : '#67c23a', fontWeight: 'bold' }">
                                        {{ row.avg_change.toFixed(2) }}%
                                    </span>
                                </template>
                            </el-table-column>
                            <el-table-column prop="count" label="数量" width="60" />
                        </el-table>
                    </el-card>
                </el-col>
                <el-col :span="12">
                    <el-card shadow="hover">
                        <template #header><b>💰 成交额 TOP10</b></template>
                        <el-table :data="topVolume" size="small" stripe style="width:100%">
                            <el-table-column label="名称" min-width="100">
                                <template #default="{ row }">
                                    <router-link :to="`/analysis?code=${row.code}`" style="color:#409eff;text-decoration:none;">{{ row.name }}</router-link>
                                </template>
                            </el-table-column>
                            <el-table-column label="行业" min-width="100">
                                <template #default="{ row }">
                                    <el-tag size="mini" effect="plain">{{ row.sector || '--' }}</el-tag>
                                </template>
                            </el-table-column>
                            <el-table-column prop="amount" label="成交额(亿)" width="100">
                                <template #default="{ row }">
                                    {{ (row.amount||0).toFixed(1) }}
                                </template>
                            </el-table-column>
                            <el-table-column prop="change_pct" label="涨跌幅" width="80">
                                <template #default="{ row }">
                                    <span :style="{ color: (row.change_pct||0) >= 0 ? '#f56c6c' : '#67c23a' }">
                                        {{ (row.change_pct||0).toFixed(2) }}%
                                    </span>
                                </template>
                            </el-table-column>
                        </el-table>
                    </el-card>
                </el-col>
            </el-row>

            <!-- 叙事分析入口 -->
            <el-card v-if="narrativesCount > 0" shadow="hover" style="margin-top:16px;border:1px solid #334;cursor:pointer;"
                @click="$router.push('/narratives')">
                <el-row :gutter="16" align="middle">
                    <el-col :span="1"><span style="font-size:24px;">🎯</span></el-col>
                    <el-col :span="5"><b>市场叙事分析</b></el-col>
                    <el-col :span="6">
                        <el-tag size="small" type="info" effect="plain">
                            发现 {{ narrativesCount }} 个叙事主题
                        </el-tag>
                    </el-col>
                    <el-col :span="8">
                        <div style="display:flex;gap:4px;flex-wrap:wrap;">
                            <el-tag v-for="(count, stage) in narrativeStageCounts" :key="stage"
                                size="small" :color="lifecycleColor(stage)" effect="dark" style="color:#fff;border:0;">
                                {{ stage }} {{ count }}
                            </el-tag>
                        </div>
                    </el-col>
                    <el-col :span="4" style="text-align:right;">
                        <el-button size="small" type="primary" text>查看详情 →</el-button>
                    </el-col>
                </el-row>
            </el-card>
        </template>

        <!-- ===== 策略信号卡片 ===== -->
        <el-card shadow="hover"
            style="margin-top:16px;border:1px solid #67c23a;">
            <template #header>
                <div style="display:flex;justify-content:space-between;align-items:center;">
                    <div>
                        <b>📡 策略信号</b>
                        <el-tag v-if="signalSummary.total" size="small" type="success" style="margin-left:8px;">
                            {{ signalSummary.triggered }}只触发
                        </el-tag>
                        <el-tag v-if="signalSummary.total" size="small" style="margin-left:4px;">
                            {{ signalSummary.total }}只扫描
                        </el-tag>
                    </div>
                    <div>
                        <el-button size="small" plain @click="showSignalConfig = !showSignalConfig"
                            style="margin-right:4px;">
                            ⚙️ 策略配置
                        </el-button>
                        <el-button size="small" type="success" plain @click="loadSignals"
                            :loading="loadingSignals">
                            🔄 刷新
                        </el-button>
                        <el-button size="small" type="primary" plain @click="triggerStrategyScan"
                            :loading="strategyScanning" :disabled="strategyScanning"
                            style="margin-left:4px;">
                            {{ strategyScanning ? '扫描中...' : '🔍 策略扫描' }}
                        </el-button>
                    </div>
                </div>
            </template>
            <!-- 策略配置面板 -->
            <div v-if="showSignalConfig" style="margin-bottom:12px;border:1px solid #ebeef5;border-radius:6px;overflow:hidden;">
                <div style="padding:8px 12px;background:#f9f9f9;font-size:13px;font-weight:bold;border-bottom:1px solid #ebeef5;">
                    维度权重配置
                </div>
                <div style="padding:8px 12px;">
                    <div v-for="(w, dim) in dimensionWeights" :key="dim"
                        style="display:flex;align-items:center;margin-bottom:6px;">
                        <div style="width:80px;font-size:13px;">{{ dimLabel[dim] || dim }}</div>
                        <el-slider v-model="dimensionWeights[dim]" :min="0.1" :max="3.0" :step="0.1"
                            style="flex:1;margin:0 12px;" @change="(v) => updateWeight(dim, v)" />
                        <div style="width:40px;text-align:right;font-size:12px;color:#909399;">{{ w.toFixed(1) }}</div>
                    </div>
                </div>
            </div>
            <!-- 信号列表 -->
            <div v-if="!signalStrategies.length" style="text-align:center;padding:24px 0;color:#909399;font-size:13px;">
                暂无信号数据，请先执行扫描
            </div>
            <div v-for="stg in signalStrategies" :key="stg.id"
                style="border:1px solid #ebeef5;border-radius:6px;margin-bottom:8px;overflow:hidden;">
                <div @click="toggleSignalExpand(stg.id)"
                    style="display:flex;align-items:center;padding:6px 12px;cursor:pointer;user-select:none;">
                    <div style="width:14px;text-align:center;color:#909399;font-size:11px;margin-right:4px;">
                        {{ signalExpandedSet.has(stg.id) ? '▼' : '▶' }}
                    </div>
                    <el-tag size="small" :type="signalDimColor(stg.dimension)" effect="plain" style="margin-right:6px;">
                        {{ stg.dimension === 'technical' ? '技术' : (stg.dimension === 'fundamental' ? '基本' : (stg.dimension === 'narrative' ? '叙事' : (stg.dimension === 'capital_flow' ? '资金' : '情绪'))) }}
                    </el-tag>
                    <div style="flex:1;font-size:13px;font-weight:bold;">{{ stg.name }}</div>
                    <div style="width:100px;text-align:right;">
                        <el-tag v-if="stg.triggered_count" size="small" :type="stg.triggered_count > 0 ? 'success' : 'info'">
                            {{ stg.triggered_count }}只信号
                        </el-tag>
                    </div>
                </div>
                <div v-if="signalExpandedSet.has(stg.id) && stg.triggered_stocks.length">
                    <div v-for="st in stg.triggered_stocks" :key="st.code"
                        style="display:flex;align-items:center;padding:4px 12px 4px 30px;border-top:1px solid #f5f5f5;font-size:12px;">
                        <router-link :to="'/analysis?code=' + st.code"
                            style="width:100px;color:#409eff;text-decoration:none;">{{ st.name }}</router-link>
                        <div style="width:40px;text-align:center;font-weight:bold;"
                            :style="{color: st.confidence >= 60 ? '#67c23a' : '#e6a23c'}">
                            {{ st.confidence }}
                        </div>
                        <div style="width:80px;text-align:center;font-size:11px;color:#909399;">
                            ￥{{ st.entry_price }}
                        </div>
                        <div style="width:80px;text-align:center;font-size:11px;color:#f56c6c;">
                            S{{ st.stop_loss }}
                        </div>
                        <div style="width:80px;text-align:center;font-size:11px;color:#67c23a;">
                            T{{ st.target_price }}
                        </div>
                        <div style="flex:1;color:#909399;overflow:hidden;text-overflow:ellipsis;white-space:nowrap;font-size:11px;"
                            :title="st.signal_detail">
                            {{ st.signal_detail }}
                        </div>
                    </div>
                </div>
            </div>
        </el-card>

        <!-- ===== 多维度评分卡片 ===== -->
        <el-card shadow="hover"
            style="margin-top:16px;border:1px solid #a78bfa;">
            <template #header>
                <div style="display:flex;justify-content:space-between;align-items:center;">
                    <div>
                        <b>🧠 多维度策略评分</b>
                        <el-tag size="small" type="success" style="margin-left:8px;">
                            {{ scoreSummary.buy_count }}只建议买入
                        </el-tag>
                        <el-tag size="small" type="warning" style="margin-left:4px;">
                            {{ scoreSummary.hold_count }}只观望
                        </el-tag>
                        <el-tag size="small" style="margin-left:4px;">
                            均分{{ scoreSummary.avg_score }}
                        </el-tag>
                    </div>
                    <div>
                        <div v-if="scanProgress" style="font-size:12px;color:#909399;margin-bottom:4px;">{{ scanProgress }}</div>
                        <el-button size="small" type="primary" plain @click="triggerScan"
                            :loading="scanning" :disabled="scanning">
                            {{ scanning ? '扫描中...' : '🔄 重新扫描' }}
                        </el-button>
                        <el-button size="small" plain @click="showScanLogs = !showScanLogs"
                            style="margin-left:6px;">
                            📋 日志
                        </el-button>
                    </div>
                </div>
            </template>
            <!-- ── 扫描日志面板 ── -->
            <div v-if="showScanLogs" style="margin-bottom:12px;border:1px solid #ebeef5;border-radius:6px;overflow:hidden;">
                <div style="padding:8px 12px;background:#f9f9f9;font-size:13px;font-weight:bold;border-bottom:1px solid #ebeef5;">📋 扫描运行日志</div>
                <div v-if="scanLogs.length === 0" style="padding:12px;text-align:center;color:#909399;font-size:12px;">
                    暂无记录，<el-button size="small" link @click="loadScanLogs">点击加载</el-button>
                </div>
                <div v-for="log in scanLogs" :key="log.id"
                    style="display:flex;align-items:center;padding:6px 12px;border-bottom:1px solid #f5f5f5;font-size:12px;">
                    <div style="width:60px;">
                        <el-tag size="small" :type="log.status === 'completed' ? 'success' : (log.status === 'running' ? 'warning' : 'danger')" effect="plain">
                            {{ log.status === 'completed' ? '完成' : (log.status === 'running' ? '运行中' : '失败') }}
                        </el-tag>
                    </div>
                    <div style="flex:1;color:#606266;">
                        {{ log.message || (log.status === 'running' ? '扫描中...' : '') }}
                    </div>
                    <div style="width:80px;text-align:right;color:#909399;">
                        {{ log.duration_seconds ? log.duration_seconds + 's' : '-' }}
                    </div>
                    <div style="width:150px;text-align:right;color:#909399;font-size:11px;">
                        {{ log.started_at ? log.started_at.substring(11, 19) : '' }}
                    </div>
                </div>
            </div>
            <!-- ── 空态 ── -->
            <div v-if="!stockScores.length" style="text-align:center;padding:32px 0;color:#909399;">
                <div style="font-size:36px;margin-bottom:8px;">🧠</div>
                <div style="margin-bottom:8px;">暂无评分数据</div>
                <el-button size="small" type="primary" @click="triggerScan" :loading="scanning">
                    {{ scanning ? '扫描中...' : '开始扫描' }}
                </el-button>
            </div>
            <div v-for="s in stockScores" :key="s.stock_code"
                style="border:1px solid #ebeef5;border-radius:6px;margin-bottom:8px;overflow:hidden;">
                <div @click="toggleExpand(s.stock_code)"
                    style="display:flex;align-items:center;padding:6px 12px;cursor:pointer;
                           border-bottom:1px solid #f0f0f0;user-select:none;">
                    <div style="width:110px;flex-shrink:0;">
                        <router-link :to="'/analysis?code=' + s.stock_code"
                            @click.stop style="color:#409eff;text-decoration:none;font-weight:bold;font-size:13px;">
                            {{ s.stock_name || s.stock_code }}
                        </router-link>
                        <div style="font-size:10px;color:#909399;">{{ s.stock_code }}</div>
                    </div>
                    <div v-for="dim in dimOrder" :key="dim" style="flex:1;text-align:center;">
                        <div style="font-size:9px;color:#909399;">{{ dimLabel[dim] }}</div>
                        <div :style="{fontSize:'14px',fontWeight:'bold',color: scoreColor(s.scores?.[dim] || 0)}">
                            {{ Math.round(s.scores?.[dim] || 0) }}
                        </div>
                    </div>
                    <div style="width:60px;text-align:center;">
                        <div style="font-size:9px;color:#909399;">综合</div>
                        <div :style="{fontSize:'18px',fontWeight:'bold',color: scoreColor(s.final_score)}">
                            {{ (s.final_score || 0).toFixed(1) }}
                        </div>
                    </div>
                    <div style="width:70px;text-align:center;">
                        <el-tag :type="decisionTag(s.decision)" size="small" effect="dark">
                            {{ decisionLabel(s.decision) }}
                        </el-tag>
                    </div>
                    <div style="width:18px;text-align:center;color:#909399;font-size:12px;">
                        {{ expandedSet.has(s.stock_code) ? '▲' : '▼' }}
                    </div>
                </div>
                <div v-if="expandedSet.has(s.stock_code)" style="padding:10px 16px;background:#fafafa;font-size:12px;">
                    <div v-for="dim in dimOrder" :key="dim" style="margin-bottom:6px;">
                        <div style="display:flex;align-items:center;gap:6px;margin-bottom:2px;">
                            <b style="width:55px;color:#606266;">{{ dimLabel[dim] }}</b>
                            <el-progress :percentage="s.scores?.[dim] || 0" :stroke-width="6"
                                :color="scoreColor(s.scores?.[dim] || 0)" style="flex:1;max-width:80px;" />
                            <span :style="{color:scoreColor(s.scores?.[dim] || 0),fontWeight:'bold'}">
                                {{ Math.round(s.scores?.[dim] || 0) }}
                            </span>
                        </div>
                        <div v-for="ev in (evidenceList(s, dim))" :key="ev.factor"
                            style="padding-left:60px;color:#606266;line-height:1.6;">
                            <span style="color:#909399;">· {{ ev.factor }}:</span>
                            <span>{{ ev.detail }}</span>
                            <span :style="{color:scoreColor(ev.score),marginLeft:'4px',fontWeight:'bold'}">
                                ({{ Math.round(ev.score) }})
                            </span>
                        </div>
                    </div>
                </div>
            </div>
        </el-card>

        <!-- 加载 / 无数据 -->
        <el-row v-if="loading" style="margin-top:40px;text-align:center;">
            <el-col><el-icon class="is-loading" :size="24"><Loading /></el-icon> 加载中...</el-col>
        </el-row>
        <el-row v-if="noData && !loading" style="margin-top:40px;text-align:center;">
            <el-col>
                <el-empty :description="noDataMsg" />
            </el-col>
        </el-row>
    </div>
</template>

<script setup>
import { ref, computed, onMounted, watch, nextTick } from 'vue'
import { getMarketOverview, getMarketDates, getSentimentCycle, getIndexHistory, getDailyNote, saveDailyNote, refreshMarketData, getMarketNarratives } from '../api/index.js'
import axios from 'axios'
import * as echarts from 'echarts'
import { ElMessage } from 'element-plus'

const loading = ref(true)
const noData = ref(false)
const noDataMsg = ref('')
const dataDate = ref('')
const dataSession = ref('close')
const sessionsAvailable = ref(['close'])
const availableDates = ref([])
const sessionsByDate = ref({})

// 情绪周期
const cycleRecords = ref([])
const currentCycleLabel = ref('')
const currentCycleStage = ref('')
const cycleAssessment = ref({})
const cycleCollapsed = ref(false)
const cycleLoading = ref(false)

// 每日操盘笔记
const dailyNote = ref('')
const editingNote = ref(false)

// 手动刷新行情
const refreshing = ref(false)

// 指数双轴图
const indexChartRef = ref(null)
let indexChartInstance = null
const indexData = ref({ hs300: [], zz500: [], ratio: [] })
const indexDays = ref(60)

// 日期选择
const selectedDate = ref(null)

const gainers = ref([])
const losers = ref([])
const hotSectors = ref([])
const topVolume = ref([])
const statCards = ref([
    { label: '上涨家数', value: '--', color: '#f56c6c', cls: '' },
    { label: '下跌家数', value: '--', color: '#67c23a', cls: '' },
    { label: '涨停', value: '--', color: '#e6a23c', cls: '' },
    { label: '跌停', value: '--', color: '#909399', cls: '' },
])

// 前后一天导航
const dateSet = computed(() => new Set(availableDates.value))
const prevDate = computed(() => {
    if (!dataDate.value || !availableDates.value.length) return null
    const idx = availableDates.value.indexOf(dataDate.value)
    return idx < availableDates.value.length - 1 ? availableDates.value[idx + 1] : null
})
const nextDate = computed(() => {
    if (!dataDate.value || !availableDates.value.length) return null
    const idx = availableDates.value.indexOf(dataDate.value)
    return idx > 0 ? availableDates.value[idx - 1] : null
})

// 市场情绪标签
const marketSentiment = computed(() => {
    if (!statCards.value.length) return { type: 'info', text: '--' }
    const up = statCards.value[0]?.value || 0
    const down = statCards.value[1]?.value || 0
    const total = up + down
    if (!total) return { type: 'info', text: '中性' }
    const ratio = up / total
    if (ratio > 0.6) return { type: 'danger', text: '🔥 普涨' }
    if (ratio < 0.4) return { type: 'success', text: '❄️ 普跌' }
    return { type: 'warning', text: '⚖️ 分化' }
})

// 不可选日期（非交易日灰掉）
function disabledDate(time) {
    const d = time.getFullYear() + '-' +
        String(time.getMonth() + 1).padStart(2, '0') + '-' +
        String(time.getDate()).padStart(2, '0')
    return !dateSet.value.has(d)
}

function toPrevDay() {
    if (prevDate.value) {
        selectedDate.value = prevDate.value
        loadData(prevDate.value)
    }
}

function toNextDay() {
    if (nextDate.value) {
        selectedDate.value = nextDate.value
        loadData(nextDate.value)
    }
}

function onDateChange(val) {
    if (val) loadData(val)
}

async function loadData(dateStr) {
    loading.value = true
    noData.value = false
    try {
        const params = {}
        if (dateStr) params.date = dateStr
        if (dataSession.value) params.session = dataSession.value
        const { data } = await getMarketOverview(params)
        if (data.status === 'no_data') {
            noData.value = true
            noDataMsg.value = data.message || '暂无行情数据'
            return
        }
        dataDate.value = data.date
        dataSession.value = data.session || 'close'
        sessionsAvailable.value = data.sessions_available || []
        const s = data.summary
        statCards.value = [
            { label: '上涨家数', value: s.up, color: '#f56c6c', cls: 'stat-up' },
            { label: '下跌家数', value: s.down, color: '#67c23a', cls: 'stat-down' },
            { label: '涨停', value: s.limit_up, color: '#e6a23c', cls: 'stat-limit' },
            { label: '跌停', value: s.limit_down, color: '#909399', cls: 'stat-limit-down' },
        ]
        gainers.value = (data.top_gainers || []).slice(0, 10)
        losers.value = (data.top_losers || []).slice(0, 10)
        hotSectors.value = (data.hot_sectors || []).slice(0, 10)
        topVolume.value = (data.top_volume || []).slice(0, 10)
    } catch (e) {
        console.error(e)
        noData.value = true
        noDataMsg.value = '加载失败'
    } finally {
        loading.value = false
    }
}

function onSessionChange(val) {
    loadData(dataDate.value)
}

// ===== 叙事分析（入口卡片） =====
const narratives = ref([])

async function loadNarratives() {
    try {
        const { data } = await getMarketNarratives()
        narratives.value = data.narratives || []
    } catch (e) {
        console.error('叙事分析加载失败', e)
    }
}

const narrativesCount = computed(() => narratives.value.length)

const narrativeStageCounts = computed(() => {
    const counts = {}
    for (const n of narratives.value) {
        const stage = n.lifecycle_stage
        counts[stage] = (counts[stage] || 0) + 1
    }
    return counts
})

function lifecycleColor(stage) {
    const m = { '萌芽': '#909399', '发酵': '#409eff', '高潮': '#e6a23c', '退潮': '#f56c6c', '证伪': '#909399' }
    return m[stage] || '#909399'
}

// ===== 情绪周期 =====
const cycleTagType = computed(() => {
    const m = { ice: 'danger', ice_recovery: 'warning', launch: 'info', fermentation: 'success', climax: 'danger', recession: 'warning', transition: 'info' }
    return m[currentCycleStage.value] || 'info'
})

function cycleTagTypeByStage(stage) {
    const m = { ice: 'danger', ice_recovery: 'warning', launch: 'info', fermentation: 'success', climax: 'danger', recession: 'warning', transition: 'info' }
    return m[stage] || 'info'
}

function cycleBgColor(stage) {
    const m = { ice: 'rgba(245,108,108,0.15)', ice_recovery: 'rgba(230,162,60,0.15)', launch: 'rgba(64,158,255,0.15)', fermentation: 'rgba(103,194,58,0.15)', climax: 'rgba(245,108,108,0.25)', recession: 'rgba(230,162,60,0.15)', transition: 'rgba(144,147,153,0.1)' }
    return m[stage] || 'rgba(144,147,153,0.1)'
}

function cycleTrendLabel(t) {
    return { rising: '📈 上升', falling: '📉 下降', flat: '➡️ 持平' }[t] || t
}

const cycleAssessmentBg = computed(() => {
    const o = cycleAssessment.value?.outlook
    if (o === 'bullish' || o === 'cautious_bullish') return 'rgba(103,194,58,0.08)'
    if (o === 'defensive' || o === 'wait_for_signal') return 'rgba(245,108,108,0.08)'
    if (o === 'watch_for_reversal') return 'rgba(230,162,60,0.08)'
    return 'rgba(144,147,153,0.06)'
})

const cycleOutlookText = computed(() => {
    const m = {
        cautious_bullish: '谨慎看多 — 情绪处于高位，注意分歧加大，建议控制仓位参与主线',
        watch_for_reversal: '警惕回调 — 情绪从高位回落，注意退潮风险，建议减仓防御',
        wait_for_signal: '等待信号 — 市场冰点，不要抄底，等反弹确认后再入场',
        recovery_emerging: '冰点反弹初现 — 小仓位试盘，确认放量再加仓',
        bullish: '积极看多 — 情绪回暖，可适当加仓参与新题材',
        defensive: '防御为主 — 情绪走弱，减仓观望，等待冰点后的机会',
        neutral: '中性观望 — 方向不明，多看少动',
    }
    return m[cycleAssessment.value?.outlook] || '观望'
})

async function loadSentimentCycle() {
    cycleLoading.value = true
    try {
        const { data } = await getSentimentCycle(30)
        cycleRecords.value = data.records || []
        currentCycleLabel.value = data.current_label || ''
        currentCycleStage.value = data.current_stage || ''
        cycleAssessment.value = data.assessment || {}
    } catch (e) {
        console.error('情绪周期加载失败', e)
    } finally {
        cycleLoading.value = false
    }
}

// ===== 指数双轴图 =====
async function loadIndexHistory() {
    try {
        const { data } = await getIndexHistory(indexDays.value)
        indexData.value = { hs300: data.hs300 || [], zz500: data.zz500 || [], ratio: data.ratio || [] }
        await nextTick()
        renderIndexChart()
    } catch (e) {
        console.error('指数数据加载失败', e)
    }
}

function renderIndexChart() {
    if (!indexChartRef.value) return
    if (!indexChartInstance) {
        indexChartInstance = echarts.init(indexChartRef.value)
    }
    const hs300 = indexData.value.hs300
    const zz500 = indexData.value.zz500
    const ratio = indexData.value.ratio
    // 对齐日期
    const dates = [...new Set([...hs300.map(d => d.date), ...zz500.map(d => d.date)])].sort()
    const hsMap = Object.fromEntries(hs300.map(d => [d.date, d.close]))
    const zzMap = Object.fromEntries(zz500.map(d => [d.date, d.close]))
    const ratioMap = Object.fromEntries(ratio.map(d => [d.date, d.ratio]))
    const hsLine = dates.map(d => hsMap[d] ?? null)
    const zzLine = dates.map(d => zzMap[d] ?? null)
    const ratioLine = dates.map(d => ratioMap[d] ?? null)
    const option = {
        tooltip: {
            trigger: 'axis',
            formatter: function(params) {
                let s = `<b>${params[0].axisValue}</b><br/>`
                params.forEach(p => {
                    if (p.value != null) {
                        const v = p.seriesName === '沪深300/中证500' ? p.value.toFixed(4) : p.value.toFixed(2)
                        s += `${p.marker} ${p.seriesName}: ${v}<br/>`
                    }
                })
                return s
            }
        },
        legend: { data: ['沪深300', '中证500', '沪深300/中证500'], top: 12 },
        grid: { left: 60, right: 140, bottom: 40, top: 60 },
        xAxis: {
            type: 'category', data: dates, axisLabel: { rotate: 45, fontSize: 10 }
        },
        yAxis: [
            { type: 'value', name: '沪深300', nameTextStyle: { color: '#5470c6' } },
            { type: 'value', name: '中证500', nameTextStyle: { color: '#91cc75' } },
            { type: 'value', name: '比值', nameTextStyle: { color: '#fc8452', padding: [0, 0, 0, 60] },
              min: 'dataMin', max: 'dataMax', splitLine: { show: false },
              axisLabel: { formatter: v => v.toFixed(3) }, position: 'right', offset: 60 },
        ],
        series: [
            {
                name: '沪深300', type: 'line', data: hsLine,
                smooth: true, symbol: 'none',
                lineStyle: { width: 2 },
                yAxisIndex: 0,
            },
            {
                name: '中证500', type: 'line', data: zzLine,
                smooth: true, symbol: 'none',
                lineStyle: { width: 2 },
                yAxisIndex: 1,
            },
            {
                name: '沪深300/中证500', type: 'line', data: ratioLine,
                smooth: true, symbol: 'none',
                lineStyle: { width: 1.5, type: 'dashed' },
                itemStyle: { color: '#fc8452' },
                yAxisIndex: 2,
            },
        ],
    }
    indexChartInstance.setOption(option, true)
}

// resize on window resize
window.addEventListener('resize', () => {
    if (indexChartInstance) indexChartInstance.resize()
})

onMounted(async () => {
    // 先获取可选日期列表
    try {
        const { data } = await getMarketDates()
        availableDates.value = data.dates || []
        sessionsByDate.value = data.sessions_by_date || {}
        selectedDate.value = data.latest || null
        // 设置默认session
        if (data.latest_sessions?.length) {
            const s = data.latest_sessions
            dataSession.value = s.includes('close') ? 'close' : s[0]
            sessionsAvailable.value = s
        }
    } catch (e) {
        console.error(e)
    }
    // 加载最新数据
    await loadData(selectedDate.value)
    // 加载情绪周期
    await loadSentimentCycle()
    // 加载指数历史
    await loadIndexHistory()
    // 加载每日笔记
    await loadDailyNote()
    // 加载叙事分析
    await loadNarratives()
    // 加载多维度评分
    await fetchStockScores()
    // 加载策略信号
    await loadSignals()
    // 加载构建版本
    await loadBuildVersion()
})

// 日期切换时重新加载笔记
watch(selectedDate, async () => {
    await loadDailyNote()
})

async function handleRefreshMarket() {
    const d = selectedDate.value || dataDate.value
    if (!d) return
    refreshing.value = true
    try {
        const { data } = await refreshMarketData(d)
        if (data.status === 'ok') {
            ElMessage.success(`✅ ${d} 行情已重新下载`)
            // 重新加载页面数据
            await loadData(d)
            await loadSentimentCycle()
            await loadIndexHistory()
        } else {
            ElMessage.error(data.message || '下载失败')
        }
    } catch (e) {
        ElMessage.error(e.response?.data?.detail || '请求失败')
    } finally {
        refreshing.value = false
    }
}

async function loadDailyNote() {
    const d = selectedDate.value || dataDate.value
    if (!d) { dailyNote.value = ''; return }
    try {
        const { data } = await getDailyNote(d)
        dailyNote.value = data.note || ''
    } catch { dailyNote.value = '' }
}

watch(editingNote, async (v) => {
    if (!v && dailyNote.value && (selectedDate.value || dataDate.value)) {
        // 退出编辑模式时自动保存
        const d = selectedDate.value || dataDate.value
        try { await saveDailyNote(d, dailyNote.value.trim()) }
        catch { /* ignore */ }
    }
})

// ===== 策略信号 =====
const signalStrategies = ref([])
const strategyScanning = ref(false)
const dimensionWeights = ref({})
const loadingSignals = ref(false)
const showSignalConfig = ref(false)
const signalExpandedSet = ref(new Set())
const buildVersion = ref({})

async function loadBuildVersion() {
    try {
        const { data } = await axios.get('/api/build-version')
        buildVersion.value = data
    } catch { /* 开发环境忽略 */ }
}

const signalSummary = computed(() => {
    const total = signalStrategies.value.length
    const triggered = signalStrategies.value.reduce((s, stg) => s + stg.triggered_count, 0)
    return { total, triggered }
})

function signalDimColor(dim) {
    const m = { technical: 'danger', fundamental: 'success', narrative: 'warning', capital_flow: '', sentiment: 'info' }
    return m[dim] || 'info'
}

function toggleSignalExpand(id) {
    const s = new Set(signalExpandedSet.value)
    if (s.has(id)) s.delete(id); else s.add(id)
    signalExpandedSet.value = s
}

async function loadSignals() {
    loadingSignals.value = true
    try {
        const { data } = await api.get("/strategy-evol/signals")
        signalStrategies.value = data.strategies || []
    } catch (e) {
        console.error("加载信号失败", e)
    } finally {
        loadingSignals.value = false
    }
}

async function updateWeight(dim, val) {
    try {
        await api.put("/strategy-evol/weights", { dimension: dim, weight: val })
    } catch (e) {
        console.error("更新权重失败", e)
    }
}

async function triggerStrategyScan() {
    if (strategyScanning.value) return
    strategyScanning.value = true
    try {
        const { data } = await api.get("/strategy-evol/strategy-scan", {
            params: { session: "close", max_stocks: 200 }
        })
        if (data.total_signals !== undefined) {
            // 扫描完成，刷新信号
            await loadSignals()
        }
    } catch (e) {
        console.error("策略扫描失败", e)
    } finally {
        strategyScanning.value = false
    }
}

// ===== 多维度评分 =====
const stockScores = ref([])
const scoring = ref(false)
const scanning = ref(false)
const scanProgress = ref("")
const showScanLogs = ref(false)
const scanLogs = ref([])
const dimOrder = ["technical", "fundamental", "narrative", "capital_flow", "sentiment"]
const dimLabel = {
    technical: "技术", fundamental: "基本",
    narrative: "叙事", capital_flow: "资金", sentiment: "情绪",
}
const expandedSet = ref(new Set())

function toggleExpand(code) {
    const s = new Set(expandedSet.value)
    if (s.has(code)) s.delete(code); else s.add(code)
    expandedSet.value = s
}

function scoreColor(s) {
    if (s >= 70) return "#67c23a"
    if (s >= 50) return "#e6a23c"
    return "#909399"
}

function decisionTag(d) {
    if (d === "STRONG_BUY" || d === "BUY") return "success"
    if (d === "HOLD") return "warning"
    return "info"
}

function decisionLabel(d) {
    if (d === "STRONG_BUY") return "强烈买入"
    if (d === "BUY") return "买入"
    if (d === "HOLD") return "观望"
    return "不进"
}

function evidenceList(s, dim) {
    try {
        const ev = typeof s.evidence === "string" ? JSON.parse(s.evidence) : (s.evidence || {})
        return ev[dim] || []
    } catch { return [] }
}

const scoreSummary = computed(() => {
    const list = stockScores.value
    let buy = 0, hold = 0, total = 0, avg = 0
    for (const s of list) {
        total++
        avg += s.final_score || 0
        if (s.decision === "BUY" || s.decision === "STRONG_BUY") buy++
        else if (s.decision === "HOLD") hold++
    }
    return {
        total, buy_count: buy, hold_count: hold,
        avg_score: total ? (avg / total).toFixed(1) : "0",
    }
})

async function fetchStockScores() {
    // 先尝试加载已有的最新结果
    try {
        const { data } = await api.get("/strategy-evol/results/latest")
        if (data.results && data.results.length) {
            stockScores.value = data.results.slice(0, 30)
            return
        }
    } catch { /* 没有结果，触发一次扫描 */ }
    // 没有已有结果，触发异步扫描
    await triggerScan()
}

// 页面加载时顺带加载扫描日志（不阻塞）
loadScanLogs()

async function triggerScan() {
    if (scanning.value) return
    scanning.value = true
    scanProgress.value = "发起扫描..."
    try {
        const { data } = await api.get("/strategy-evol/scan?session=close&max_stocks=20")
        const batchId = data.batch_id
        // 轮询进度
        let tries = 0
        while (tries < 60) {  // 最多等5分钟
            await new Promise(r => setTimeout(r, 5000))
            const { data: st } = await api.get("/strategy-evol/scan/status")
            const p = st.progress || {}
            scanProgress.value = `扫描中 ${p.scored || 0}/${p.total || "?"} 只 (失败${p.failures || 0})`
            if (!st.running) break
            tries++
        }
        // 扫描完成，加载结果
        const { data: res } = await api.get("/strategy-evol/results/latest")
        stockScores.value = (res.results || []).slice(0, 30)
        scanProgress.value = ""
    } catch (e) {
        console.error("扫描失败", e)
        scanProgress.value = "扫描失败"
    } finally {
        scanning.value = false
        scoring.value = false
        // 展开日志面板并加载日志
        showScanLogs.value = true
        await loadScanLogs()
    }
}

async function loadScanLogs() {
    try {
        const { data } = await api.get("/strategy-evol/scan/logs?limit=10")
        scanLogs.value = data.logs || []
    } catch { /* ignore */ }
}
</script>

<style scoped>
.dashboard { max-width: 1400px; margin: 0 auto; }
.stat-card { text-align: center; }
.stat-card :deep(.el-card__body) { padding: 20px; }
.stat-value { font-size: 32px; font-weight: bold; }
.stat-label { font-size: 14px; color: #909399; margin-top: 4px; }
.stat-up { border-top: 3px solid #f56c6c; }
.stat-down { border-top: 3px solid #67c23a; }
.stat-limit { border-top: 3px solid #e6a23c; }
.stat-limit-down { border-top: 3px solid #909399; }
</style>
