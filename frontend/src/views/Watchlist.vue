<template>
    <div class="watchlist-page">
        <!-- ==================== 三栏布局 ==================== -->
        <el-row :gutter="12">
            <!-- ① 左侧：选中股票的详情 -->
            <el-col :span="11">
                <template v-if="!selected">
                    <el-empty description="请从右侧观察池选择一只股票" :image-size="80" />
                </template>

                <template v-else>
                    <!-- ①-a 多备注时间线 -->
                    <el-card shadow="hover" style="margin-bottom:12px;" :style="{ borderLeft: '4px solid #409eff' }">
                        <template #header>
                            <div style="display:flex;justify-content:space-between;align-items:center;">
                                <b>📝 备注 ({{ stockNotes.length }})</b>
                                <el-button size="small" type="primary" plain @click="showAddNoteInput = !showAddNoteInput">
                                    {{ showAddNoteInput ? '收起' : '+ 写备注' }}
                                </el-button>
                            </div>
                        </template>
                        <!-- 新增备注输入 -->
                        <div v-if="showAddNoteInput" style="margin-bottom:12px;">
                            <el-input v-model="newNoteText" type="textarea" :rows="2"
                                placeholder="写一条观察笔记、交易计划、分析结论..." />
                            <div style="margin-top:6px;display:flex;justify-content:flex-end;gap:6px;">
                                <el-button size="small" @click="showAddNoteInput = false; newNoteText = ''">取消</el-button>
                                <el-button size="small" type="primary" @click="handleAddNote" :disabled="!newNoteText.trim()">添加备注</el-button>
                            </div>
                        </div>
                        <!-- 备注列表 -->
                        <div v-if="stockNotes.length" class="note-timeline">
                            <div v-for="(note, i) in stockNotes" :key="note.id || i" class="note-item">
                                <div class="note-dot"></div>
                                <div class="note-body">
                                    <div class="note-meta">
                                        <span class="note-date">{{ note.created_at }}</span>
                                        <el-button size="mini" type="danger" link
                                            @click="handleDeleteNote(note)">删除</el-button>
                                    </div>
                                    <div class="note-text">{{ note.note }}</div>
                                </div>
                            </div>
                        </div>
                        <div v-else style="color:#909399;font-size:13px;padding:8px 0;">
                            暂无备注，点击「+ 写备注」添加第一条
                        </div>
                    </el-card>

                    <!-- ①-b 操作栏（始终显示） -->
                    <div style="display:flex;align-items:center;gap:8px;margin-bottom:12px;flex-wrap:wrap;"
                        :style="{ borderLeft: profileData && profileData.risk_passed ? '4px solid #67c23a' : profileData && profileData.risk_passed === false ? '4px solid #f56c6c' : '4px solid #909399', paddingLeft: '10px' }">
                        <el-tag v-if="profileData && profileData.risk_passed === true" type="success" size="small" effect="dark">✅ 通过</el-tag>
                        <el-tag v-else-if="profileData && profileData.risk_passed === false" type="danger" size="small" effect="dark">❌ 禁止买入</el-tag>
                        <el-tag v-else type="info" size="small" effect="dark">⏳ 待分析</el-tag>
                        <el-tag v-if="selected.market" size="small" type="warning" effect="plain">
                            {{ selected.market === 'us_stock' ? '🇺🇸 美股' : selected.market === 'hk_stock' ? '🇭🇰 港股' : '🇨🇳 A股' }}
                        </el-tag>
                        <b style="font-size:14px;">{{ selected.name }} ({{ selected.code }})</b>
                        <span v-if="profileData?.price" style="color:#909399;font-size:12px;">
                            现价 {{ profileData.price?.toFixed(2) }}
                        </span>
                        <span v-if="profileData?.change_pct !== null && profileData?.change_pct !== undefined" :style="{ color: (profileData.change_pct||0) >= 0 ? '#f56c6c' : '#67c23a', fontSize:'12px' }">
                            {{ (profileData.change_pct||0) >= 0 ? '+' : '' }}{{ (profileData.change_pct||0).toFixed(2) }}%
                        </span>
                        <div style="flex:1"></div>
                        <el-button size="small" @click="goAnalysis">🔍 分析</el-button>
                        <el-button size="small" type="success" @click="openBuyDialog">💰 买入</el-button>
                        <el-popconfirm v-if="isInPositions" title="确定卖出？" @confirm="handleSell">
                            <template #reference>
                                <el-button size="small" type="danger">💸 卖出</el-button>
                            </template>
                        </el-popconfirm>
                        <div style="display:flex;gap:4px;">
                            <el-tag v-for="opt in [{v:'high',l:'高',t:'danger'},{v:'medium',l:'中',t:'warning'},{v:'low',l:'低',t:'info'}]" :key="opt.v"
                                size="small"
                                :type="selected.priority === opt.v ? opt.t : 'info'"
                                :effect="selected.priority === opt.v ? 'dark' : 'plain'"
                                style="cursor:pointer;"
                                @click="setPriority(opt.v)">
                                {{ opt.l }}
                            </el-tag>
                        </div>
                        <el-popconfirm title="确定移除？" @confirm="handleRemove(selected.code)">
                            <template #reference>
                                <el-button size="small" type="danger">移除</el-button>
                            </template>
                        </el-popconfirm>
                    </div>

                    <!-- ①-b' 提醒系统 -->
                    <el-card shadow="hover" style="margin-bottom:12px;" :style="{ borderLeft: '4px solid #e6a23c' }">
                        <template #header>
                            <div style="display:flex;justify-content:space-between;align-items:center;">
                                <b>⏰ 提醒 ({{ stockReminders.length }})</b>
                                <el-button size="small" type="warning" plain @click="showAddReminderInput = !showAddReminderInput">
                                    {{ showAddReminderInput ? '收起' : '+ 提醒' }}
                                </el-button>
                            </div>
                        </template>
                        <!-- 新建提醒表单 -->
                        <div v-if="showAddReminderInput" style="margin-bottom:12px;">
                            <el-form label-width="70px" size="small">
                                <el-form-item label="类型">
                                    <el-radio-group v-model="reminderForm.type">
                                        <el-radio value="price">价格</el-radio>
                                        <el-radio value="time">时间</el-radio>
                                    </el-radio-group>
                                </el-form-item>
                                <el-form-item :label="reminderForm.type === 'price' ? '条件' : '日期'">
                                    <div v-if="reminderForm.type === 'price'" style="display:flex;gap:6px;">
                                        <el-select v-model="reminderForm.condition" style="width:100px;">
                                            <el-option label="≥" value="above" />
                                            <el-option label="≤" value="below" />
                                        </el-select>
                                        <el-input-number v-model="reminderForm.priceValue" :min="0.01" :step="0.01" :precision="2" style="flex:1;" placeholder="目标价格" />
                                    </div>
                                    <el-date-picker v-else v-model="reminderForm.dateValue" type="datetime"
                                        placeholder="选择提醒时间" style="width:100%;"
                                        value-format="YYYY-MM-DD HH:mm" />
                                </el-form-item>
                                <el-form-item label="备注">
                                    <el-input v-model="reminderForm.noteText" placeholder="提醒的目的或备注" />
                                </el-form-item>
                            </el-form>
                            <div style="display:flex;justify-content:flex-end;gap:6px;">
                                <el-button size="small" @click="showAddReminderInput = false; resetReminderForm()">取消</el-button>
                                <el-button size="small" type="warning" @click="handleAddReminder"
                                    :disabled="!canAddReminder">创建提醒</el-button>
                            </div>
                        </div>
                        <!-- 提醒列表 -->
                        <div v-if="stockReminders.length" class="reminder-list">
                            <div v-for="r in stockReminders" :key="r.id" class="reminder-item"
                                :class="{ 'reminder-triggered': r.triggered, 'reminder-disabled': !r.enabled }">
                                <div class="reminder-icon">
                                    <el-tag v-if="r.type === 'price'" size="small" :type="r.triggered ? 'info' : 'warning'" effect="dark">💰</el-tag>
                                    <el-tag v-else size="small" :type="r.triggered ? 'info' : 'warning'">⏰</el-tag>
                                </div>
                                <div class="reminder-body">
                                    <div class="reminder-target">
                                        <template v-if="r.type === 'price'">
                                            <span v-if="r.condition === 'above'">📈 涨破 </span>
                                            <span v-else>📉 跌破 </span>
                                            <b>¥{{ parseFloat(r.target_value).toFixed(2) }}</b>
                                        </template>
                                        <template v-else>
                                            🗓️ <b>{{ r.target_value }}</b>
                                        </template>
                                        <el-tag v-if="r.triggered" size="mini" type="success" effect="dark" style="margin-left:6px;">已触发</el-tag>
                                        <el-tag v-else-if="!r.enabled" size="mini" type="info" style="margin-left:6px;">已暂停</el-tag>
                                    </div>
                                    <div v-if="r.note_text" class="reminder-note">{{ r.note_text }}</div>
                                    <div class="reminder-meta">
                                        <span class="reminder-date">创建于 {{ r.created_at }}</span>
                                        <div style="flex:1"></div>
                                        <el-button size="mini" type="warning" link @click="handleToggleReminder(r)">
                                            {{ r.enabled ? '暂停' : '启用' }}
                                        </el-button>
                                        <el-button size="mini" type="danger" link @click="handleDeleteReminder(r)">删除</el-button>
                                    </div>
                                </div>
                            </div>
                        </div>
                        <div v-else style="color:#909399;font-size:13px;padding:8px 0;">
                            暂无提醒，点击「+ 提醒」创建价格或时间提醒
                        </div>
                    </el-card>

                    <!-- ①-b'' AI预测 -->
                    <el-card shadow="hover" style="margin-bottom:12px;" :style="{ borderLeft: '4px solid #9b59b6' }">
                        <template #header>
                            <div style="display:flex;justify-content:space-between;align-items:center;">
                                <b>🔮 AI趋势预测</b>
                                <el-button size="small" type="primary" plain
                                    @click="handlePredict"
                                    :loading="predicting"
                                    :disabled="predicting">
                                    {{ predicting ? '分析中...' : '运行预测' }}
                                </el-button>
                            </div>
                        </template>
                        <!-- 加载中 -->
                        <div v-if="predicting" style="text-align:center;padding:20px;">
                            <el-icon class="is-loading" :size="24"><Loading /></el-icon>
                            <p style="color:#909399;font-size:13px;margin-top:8px;">正在分析历史周期和形态...</p>
                        </div>
                        <!-- 预测结果 -->
                        <div v-else-if="prediction" class="prediction-result">
                            <!-- 方向 + 置信度 -->
                            <div style="display:flex;align-items:center;gap:12px;margin-bottom:12px;">
                                <el-tag v-if="prediction.prediction?.trend_direction === '看涨'"
                                    type="success" size="large" effect="dark" style="font-size:16px;padding:4px 12px;">
                                    📈 {{ prediction.prediction.trend_direction }}
                                </el-tag>
                                <el-tag v-else-if="prediction.prediction?.trend_direction === '看跌'"
                                    type="danger" size="large" effect="dark" style="font-size:16px;padding:4px 12px;">
                                    📉 {{ prediction.prediction.trend_direction }}
                                </el-tag>
                                <el-tag v-else-if="prediction.prediction?.trend_direction === '震荡'"
                                    type="warning" size="large" effect="dark" style="font-size:16px;padding:4px 12px;">
                                    〰️ {{ prediction.prediction.trend_direction }}
                                </el-tag>
                                <el-progress v-if="prediction.prediction?.confidence != null"
                                    type="circle" :percentage="prediction.prediction.confidence"
                                    :width="50" :stroke-width="4"
                                    :color="prediction.prediction.confidence >= 70 ? '#67c23a' : prediction.prediction.confidence >= 50 ? '#e6a23c' : '#909399'" />
                                <el-tag v-if="prediction.prediction?.cycle_phase" type="info" effect="plain">
                                    {{ prediction.prediction.cycle_phase }}
                                </el-tag>
                            </div>
                            <!-- 目标价 -->
                            <div v-if="prediction.prediction?.target_price" style="display:flex;gap:16px;margin-bottom:10px;">
                                <div v-if="prediction.prediction.target_price.up" style="background:#fef0f0;padding:6px 12px;border-radius:6px;">
                                    <span style="color:#f56c6c;font-size:12px;">📈 目标上限</span>
                                    <div style="font-weight:bold;color:#f56c6c;">¥{{ prediction.prediction.target_price.up.toFixed(2) }}</div>
                                </div>
                                <div v-if="prediction.prediction.target_price.down" style="background:#f0f9eb;padding:6px 12px;border-radius:6px;">
                                    <span style="color:#67c23a;font-size:12px;">📉 目标下限</span>
                                    <div style="font-weight:bold;color:#67c23a;">¥{{ prediction.prediction.target_price.down.toFixed(2) }}</div>
                                </div>
                                <div style="background:#f5f7fa;padding:6px 12px;border-radius:6px;">
                                    <span style="color:#909399;font-size:12px;">💰 现价</span>
                                    <div style="font-weight:bold;">¥{{ prediction.current_price }}</div>
                                </div>
                            </div>
                            <!-- 关键位 -->
                            <div v-if="prediction.prediction?.key_levels" style="display:flex;gap:16px;margin-bottom:10px;font-size:12px;">
                                <div><span style="color:#67c23a;">🛡️ 支撑: </span>{{ prediction.prediction.key_levels.support?.join(' / ') }}</div>
                                <div><span style="color:#f56c6c;">🚧 阻力: </span>{{ prediction.prediction.key_levels.resistance?.join(' / ') }}</div>
                            </div>
                            <!-- 推理 -->
                            <div v-if="prediction.prediction?.reasoning" style="font-size:13px;color:#303133;line-height:1.6;margin-bottom:8px;background:#f5f7fa;padding:10px;border-radius:6px;">
                                {{ prediction.prediction.reasoning }}
                            </div>
                            <!-- 风险提示 -->
                            <div v-if="prediction.prediction?.risk_warning" style="font-size:12px;color:#e6a23c;background:#fdf6ec;padding:6px 10px;border-radius:4px;">
                                ⚠️ {{ prediction.prediction.risk_warning }}
                            </div>
                            <!-- 近期形态 -->
                            <div v-if="prediction.patterns?.length" style="margin-top:8px;display:flex;flex-wrap:wrap;gap:4px;">
                                <el-tag v-for="(p, pi) in prediction.patterns" :key="pi" size="mini" type="info" effect="plain">{{ p }}</el-tag>
                            </div>
                        </div>
                        <div v-else-if="!predicting" style="color:#909399;font-size:13px;padding:12px 0;text-align:center;">
                            点击「运行预测」，基于历史周期+K线形态+AI推理判断未来方向
                        </div>
                    </el-card>

                    <!-- ①-c 技术面详情（有数据时才显示） -->
                    <el-card v-if="profileData" shadow="hover" style="margin-bottom:12px;">
                        <el-descriptions :column="4" border size="mini">
                            <el-descriptions-item label="行业">{{ profileData.sector || '--' }}</el-descriptions-item>
                            <el-descriptions-item label="MA5">{{ profileData.ma5?.toFixed(2) || '--' }}</el-descriptions-item>
                            <el-descriptions-item label="MA20">{{ profileData.ma20?.toFixed(2) || '--' }}</el-descriptions-item>
                            <el-descriptions-item label="MA60">{{ profileData.ma60?.toFixed(2) || '--' }}</el-descriptions-item>
                            <el-descriptions-item label="MA200">{{ profileData.ma200?.toFixed(2) || '--' }}</el-descriptions-item>
                            <el-descriptions-item label="RSI14">{{ profileData.rsi14 || '--' }}</el-descriptions-item>
                            <el-descriptions-item label="均线多头">
                                <el-tag :type="profileData.bullish_alignment ? 'success' : 'info'" size="small">{{ profileData.bullish_alignment ? '是' : '否' }}</el-tag>
                            </el-descriptions-item>
                            <el-descriptions-item label="关注理由">{{ selected.reason || '--' }}</el-descriptions-item>
                        </el-descriptions>
                    </el-card>
                    <div v-else-if="analyzing" style="text-align:center;padding:30px;">
                        <el-icon class="is-loading" :size="24"><Loading /></el-icon>
                        <p style="color:#909399;font-size:13px;margin-top:8px;">正在分析...</p>
                    </div>
                    <div v-else style="text-align:center;padding:30px;color:#909399;font-size:13px;">
                        点击「立即分析」获取技术面数据
                    </div>
                </template>
            </el-col>

            <!-- ② 中间：选中股票的历次分析记录 -->
            <el-col :span="7">
                <template v-if="!selected">
                    <el-empty description="请先选择一只股票" :image-size="60" />
                </template>

                <template v-else>
                    <el-card shadow="hover" class="panel-history">
                        <template #header>
                            <div style="display:flex;justify-content:space-between;align-items:center;">
                                <b>📋 {{ selected.name }} 历次分析 ({{ stockHistory.length }})</b>
                                <div>
                                    <el-button size="small" type="warning" plain @click="handleSaveSnapshot" :loading="savingSnapshot">💾 保存快照</el-button>
                                    <el-button v-if="stockHistory.length" size="small" type="primary" plain @click="loadStockHistory">刷新</el-button>
                                </div>
                            </div>
                        </template>

                        <div v-if="stockHistory.length" class="scroll-area">
                            <div v-for="(rec, i) in stockHistory" :key="'h' + i"
                                class="history-item"
                                :class="{ 'history-active': detailHist?.code === rec.code && detailHist?.analysis_date === rec.analysis_date }"
                                @click="goToHistoryAnalysis(rec)">
                                <div class="history-header">
                                    <el-tag v-if="rec.record_type === 'draft'" size="mini" type="warning" effect="dark">草稿</el-tag>
                                    <el-tag v-else size="mini" type="primary" effect="dark">快照</el-tag>
                                    <el-tag size="mini" :type="rec.risk_passed ? 'success' : 'danger'" effect="dark">
                                        {{ rec.risk_passed ? 'PASS' : 'FAIL' }}
                                    </el-tag>
                                    <el-tag v-if="getTrendStatus(rec) === '多头'" size="mini" type="success" plain>多头</el-tag>
                                    <el-tag v-else-if="getTrendStatus(rec) === '偏多'" size="mini" type="warning" plain>偏多</el-tag>
                                    <el-tag v-else-if="getTrendStatus(rec) === '偏空'" size="mini" type="danger" plain>偏空</el-tag>
                                    <el-tag v-else-if="getTrendStatus(rec) === '空头'" size="mini" type="danger" effect="dark">空头</el-tag>
                                    <el-tag v-else size="mini" type="info" plain>震荡</el-tag>
                                    <span class="history-date">{{ rec.analysis_date }}</span>
                                    <div style="flex:1"></div>
                                    <el-popconfirm v-if="rec.record_type === 'snapshot'" title="确定删除此快照？" @confirm="handleDeleteSnapshot(rec)">
                                        <template #reference>
                                            <el-button size="mini" type="danger" link @click.stop>删除</el-button>
                                        </template>
                                    </el-popconfirm>
                                    <el-popconfirm v-else title="确定删除此草稿？" @confirm="handleDeleteDraft(rec)">
                                        <template #reference>
                                            <el-button size="mini" type="danger" link @click.stop>删除</el-button>
                                        </template>
                                    </el-popconfirm>
                                </div>
                                <div class="history-meta">
                                    <span style="font-weight:bold;">¥{{ rec.price?.toFixed(2) || '--' }}</span>
                                    <span :style="{ color: (rec.change_pct||0) >= 0 ? '#f56c6c' : '#67c23a' }">
                                        {{ (rec.change_pct||0) >= 0 ? '+' : '' }}{{ rec.change_pct?.toFixed(2) }}%
                                    </span>
                                    <span style="color:#909399;">
                                        MA5:{{ rec.ma5?.toFixed(1) || '--' }} MA20:{{ rec.ma20?.toFixed(1) || '--' }}
                                    </span>
                                    <span style="color:#909399;">RSI:{{ rec.rsi14 || '--' }}</span>
                                </div>
                            </div>
                        </div>

                        <div v-else style="text-align:center;padding:24px;color:#909399;font-size:13px;">
                            <p>暂无分析记录</p>
                            <p style="margin-top:4px;">点击「立即分析」生成第一条</p>
                        </div>
                    </el-card>
                </template>
            </el-col>

            <!-- ③ 右侧：观察池列表（按市场+行业分组） -->
            <el-col :span="6">
                <el-card shadow="hover" class="panel-list">
                    <template #header>
                        <div style="display:flex;justify-content:space-between;align-items:center;">
                            <b>🔭 观察池 ({{ items.length }})</b>
                            <el-button size="small" type="primary" plain @click="showAddDialog = true">+</el-button>
                        </div>
                    </template>
                    <!-- 市场筛选 -->
                    <div style="display:flex;gap:4px;margin-bottom:10px;flex-wrap:wrap;">
                        <el-tag v-for="opt in marketOptions" :key="opt"
                            size="small"
                            :type="marketFilter === opt ? 'primary' : 'info'"
                            :effect="marketFilter === opt ? 'dark' : 'plain'"
                            style="cursor:pointer;"
                            @click="marketFilter = opt">
                            {{ opt }}
                        </el-tag>
                    </div>
                    <div style="margin-bottom:8px;">
                        <el-input v-model="watchlistSearch" placeholder="搜索名称或代码..." size="small" prefix-icon="Search" clearable />
                    </div>
                    <div v-if="items.length" class="scroll-area">
                        <template v-for="(group, gi) in groupedItems" :key="gi">
                            <!-- 市场标题（首次出现该市场时显示） -->
                            <div v-if="gi === 0 || groupedItems[gi-1].market !== group.market"
                                style="font-size:13px;font-weight:bold;color:#909399;padding:6px 4px 2px;border-top:1px solid #eee;margin-top:4px;">
                                {{ group.market }}
                            </div>
                            <!-- 行业分组标题 -->
                            <div style="font-size:12px;color:#b0b0b0;padding:4px 4px 2px 8px;">
                                📂 {{ group.industry }}
                                <span style="color:#909399;">({{ group.items.length }})</span>
                            </div>
                            <!-- 行业内的股票列表 -->
                            <div v-for="item in group.items" :key="item.code"
                                class="watch-item"
                                :class="'priority-' + item.priority"
                                @click="selectItem(item)"
                                :style="{ background: selected?.code === item.code ? '#ecf5ff' : '' }">
                                <div class="watch-code">
                                    <el-tag size="small" :type="pType(item.priority)" effect="dark" style="margin-right:4px;">
                                        {{ pLabel(item.priority) }}
                                    </el-tag>
                                    {{ item.code }}
                                </div>
                                <div class="watch-name">{{ item.name }}</div>
                                <div class="watch-sector" v-if="item.sector">{{ item.sector }}</div>
                            </div>
                        </template>
                    </div>
                    <el-empty v-else description="观察池为空" :image-size="60" />
                </el-card>
            </el-col>
        </el-row>

        <!-- ==================== 买入对话框 ==================== -->
        <el-dialog v-model="showBuyDialog" title="💰 买入" width="360px" @close="onBuyDialogClose">
            <el-form label-width="70px">
                <el-form-item label="股票">
                    <span style="font-weight:bold;">{{ selected?.name }} ({{ selected?.code }})</span>
                </el-form-item>
                <el-form-item label="数量">
                    <el-input-number v-model="buyQty" :min="1" :step="100" style="width:100%" />
                </el-form-item>
                <el-form-item label="成本价">
                    <el-input-number v-model="buyCost" :min="0.01" :step="0.01" :precision="2" style="width:100%" />
                </el-form-item>
                <el-form-item label="合计">
                    <span style="font-weight:bold;font-size:16px;">¥ {{ (buyQty * buyCost).toFixed(2) }}</span>
                </el-form-item>
            </el-form>
            <template #footer>
                <el-button @click="showBuyDialog = false">取消</el-button>
                <el-button type="primary" @click="handleBuy" :loading="adding">确认买入</el-button>
            </template>
        </el-dialog>

        <!-- ==================== 添加股票对话框 ==================== -->
        <el-dialog v-model="showAddDialog" title="➕ 添加股票到观察池" width="480px">
            <el-form :model="form" label-width="60px" @submit.prevent>
                <el-form-item label="搜索">
                    <el-autocomplete
                        v-model="searchText"
                        :fetch-suggestions="querySearch"
                        :trigger-on-focus="false"
                        placeholder="输入代码、名称或拼音首字母搜索"
                        style="width:100%"
                        @select="handleSelect"
                        clearable
                        :debounce="300">
                        <template #default="{ item }">
                            <div style="display:flex;align-items:center;justify-content:space-between;">
                                <div>
                                    <span style="font-weight:bold;">{{ item.code }}</span>
                                    <span style="margin-left:8px;">{{ item.name }}</span>
                                </div>
                                <el-tag size="mini" effect="plain" type="info">
                                    {{ item.pinyin_initials || (item.market||'') }}
                                </el-tag>
                            </div>
                        </template>
                    </el-autocomplete>
                </el-form-item>
                <el-form-item label="代码">
                    <el-input v-model="form.code" disabled placeholder="从搜索中选择" />
                </el-form-item>
                <el-form-item label="名称">
                    <el-input v-model="form.name" disabled placeholder="从搜索中选择" />
                </el-form-item>
                <el-form-item label="优先级">
                    <el-select v-model="form.priority" style="width:100%">
                        <el-option label="🔴 高优先" value="high" />
                        <el-option label="🟡 中优先" value="medium" />
                        <el-option label="🟢 低优先" value="low" />
                    </el-select>
                </el-form-item>
                <el-form-item label="理由"><el-input v-model="form.reason" placeholder="关注理由" /></el-form-item>
            </el-form>
            <template #footer>
                <el-button @click="showAddDialog = false">取消</el-button>
                <el-button type="primary" @click="handleAdd" :disabled="!form.code" :loading="adding">添加</el-button>
            </template>
        </el-dialog>

        <!-- ==================== 历次分析详情对话框 ==================== -->
        <el-dialog v-model="showDetailDialog" :title="detailTitle" width="680px" top="5vh">
            <template v-if="detailHist">
                <!-- 顶部状态 -->
                <div style="display:flex;align-items:center;gap:10px;margin-bottom:16px;flex-wrap:wrap;">
                    <el-tag :type="detailHist.risk_passed ? 'success' : 'danger'" size="medium" effect="dark">
                        {{ detailHist.risk_passed ? '✅ 风控通过' : '❌ 禁止买入' }}
                    </el-tag>
                    <el-tag :type="detailTagType(detailHist)" size="medium">
                        {{ detailTagLabel(detailHist) }}
                    </el-tag>
                    <span style="color:#909399;font-size:13px;">分析日期：{{ detailHist.analysis_date }}</span>
                    <span v-if="detailHist.sector" style="color:#909399;font-size:13px;">{{ detailHist.sector }}</span>
                </div>

                <!-- 技术面快照 -->
                <el-card shadow="hover" style="margin-bottom:12px;">
                    <template #header><b>📊 当时技术面快照</b></template>
                    <el-descriptions :column="4" border size="mini">
                        <el-descriptions-item label="当时价">
                            <span style="font-weight:bold;font-size:15px;">¥{{ detailHist.price?.toFixed(2) || '--' }}</span>
                        </el-descriptions-item>
                        <el-descriptions-item label="涨幅">
                            <span :style="{ color: (detailHist.change_pct||0) >= 0 ? '#f56c6c' : '#67c23a', fontWeight:'bold' }">
                                {{ (detailHist.change_pct||0) >= 0 ? '+' : '' }}{{ detailHist.change_pct?.toFixed(2) }}%
                            </span>
                        </el-descriptions-item>
                        <el-descriptions-item label="MA5">{{ detailHist.ma5?.toFixed(2) || '--' }}</el-descriptions-item>
                        <el-descriptions-item label="MA10">{{ detailHist.ma10?.toFixed(2) || '--' }}</el-descriptions-item>
                        <el-descriptions-item label="MA20">{{ detailHist.ma20?.toFixed(2) || '--' }}</el-descriptions-item>
                        <el-descriptions-item label="MA60">{{ detailHist.ma60?.toFixed(2) || '--' }}</el-descriptions-item>
                        <el-descriptions-item label="MA200">{{ detailHist.ma200?.toFixed(2) || '--' }}</el-descriptions-item>
                        <el-descriptions-item label="RSI(14)">{{ detailHist.rsi14 || '--' }}</el-descriptions-item>
                        <el-descriptions-item label="MACD(DIF)">{{ detailHist.macd_dif?.toFixed(4) || '--' }}</el-descriptions-item>
                        <el-descriptions-item label="MACD(DEA)">{{ detailHist.macd_dea?.toFixed(4) || '--' }}</el-descriptions-item>
                        <el-descriptions-item label="MACD(柱)" :span="2">
                            <span :style="{ color: (detailHist.macd_hist||0) >= 0 ? '#f56c6c' : '#67c23a' }">
                                {{ detailHist.macd_hist?.toFixed(4) || '--' }}
                            </span>
                        </el-descriptions-item>
                    </el-descriptions>
                </el-card>

                <!-- 基本面快照 -->
                <el-card v-if="detailHist.revenue || detailHist.net_profit" shadow="hover">
                    <template #header><b>💰 当时基本面快照</b></template>
                    <el-descriptions :column="4" border size="mini">
                        <el-descriptions-item label="营收">{{ detailHist.revenue || '--' }}</el-descriptions-item>
                        <el-descriptions-item label="净利">{{ detailHist.net_profit || '--' }}</el-descriptions-item>
                        <el-descriptions-item label="毛利率">{{ detailHist.gross_margin != null ? detailHist.gross_margin + '%' : '--' }}</el-descriptions-item>
                        <el-descriptions-item label="ROE">{{ detailHist.roe != null ? detailHist.roe + '%' : '--' }}</el-descriptions-item>
                    </el-descriptions>
                </el-card>

                <el-empty v-if="!detailHist.price && !detailHist.ma5" :image-size="40" description="该记录数据不完整" />
            </template>
        </el-dialog>
    </div>
</template>

<script setup>
import { ref, computed, onMounted, watch } from 'vue'
import { getWatchlist, addWatchItem, removeWatchItem, updateWatchItem, getStockProfile, searchStockInfo, saveSnapshot, deleteSnapshot, deleteDraft, addPosition, deletePosition, getPositions, addStockNote, deleteStockNote, getStockReminders, addStockReminder, deleteStockReminder, toggleStockReminder, getAllActiveReminders, predictStockTrend } from '../api/index.js'
import { useRouter } from 'vue-router'
import { ElMessage } from 'element-plus'
import { Search } from '@element-plus/icons-vue'

const router = useRouter()

// ===== 观察池 =====
const items = ref([])
const selected = ref(null)
const adding = ref(false)
const savingSnapshot = ref(false)
const showAddDialog = ref(false)
const form = ref({ code: '', name: '', priority: 'medium', reason: '' })
const searchText = ref('')
const watchlistSearch = ref('')

// ===== 持仓（对接仓位管理）=====
const positionsList = ref([])
const showBuyDialog = ref(false)
const buyQty = ref(100)
const buyCost = ref(0)
const isInPositions = computed(() => {
    if (!selected.value?.code) return false
    return positionsList.value.some(p => p.code === selected.value.code)
})

onMounted(async () => {
    await loadData()
    await loadPositions()
})

async function loadPositions() {
    try {
        const { data } = await getPositions()
        positionsList.value = data.positions || []
    } catch { positionsList.value = [] }
}

function openBuyDialog() {
    buyCost.value = profileData.value?.price || selected.value?.last_price || 0
    buyQty.value = 100
    showBuyDialog.value = true
}

async function handleBuy() {
    if (!selected.value || !buyQty.value || !buyCost.value) return
    try {
        await addPosition({
            code: selected.value.code,
            name: selected.value.name,
            quantity: buyQty.value,
            cost_price: buyCost.value,
        })
        ElMessage.success(`已买入 ${selected.value.name} ${buyQty.value}股 @ ¥${buyCost.value}`)
        showBuyDialog.value = false
        await loadPositions()
    } catch (e) {
        ElMessage.error(e.response?.data?.detail || '买入失败')
    }
}

async function handleSell() {
    if (!selected.value) return
    try {
        await deletePosition(selected.value.code)
        ElMessage.success(`已卖出 ${selected.value.name}`)
        await loadPositions()
    } catch {
        ElMessage.error('卖出失败')
    }
}

// 买入弹窗
function onBuyDialogClose() { showBuyDialog.value = false }

// 市场筛选（全部/A股/港股/美股）
const marketFilter = ref('全部')
const marketOptions = ['全部', 'A股', '港股', '美股']

// 按市场和行业分组
const groupedItems = computed(() => {
    const list = items.value || []
    // 过滤
    let filtered = list
    // 搜索过滤
    const sq = (watchlistSearch.value || '').trim().toLowerCase()
    if (sq) {
        filtered = filtered.filter(i =>
            (i.code || '').toLowerCase().includes(sq) ||
            (i.name || '').toLowerCase().includes(sq)
        )
    }
    // 市场过滤
    if (marketFilter.value !== '全部') {
        filtered = list.filter(i => {
            const mkt = (i.market || '').toLowerCase()
            if (marketFilter.value === '美股') return mkt === 'us_stock'
            if (marketFilter.value === '港股') return mkt === 'hk_stock'
            if (marketFilter.value === 'A股') return !mkt || ['us_stock','hk_stock'].includes(mkt) === false
            return true
        })
    }
    // 分组：市场 → 行业
    const groups = {}
    for (const item of filtered) {
        const mkt = (item.market || '').toLowerCase()
        const marketGroup = mkt === 'us_stock' ? '🇺🇸 美股'
            : mkt === 'hk_stock' ? '🇭🇰 港股'
            : '🇨🇳 A股'
        // 行业清洗：美股行业可能是"美股"这种无意义的值
        let industry = (item.industry || item.sector || '').trim()
        if (!industry || industry === '美股' || industry === '港股') {
            industry = '其他'
        }
        const groupKey = `${marketGroup}||${industry}`
        if (!groups[groupKey]) {
            groups[groupKey] = { market: marketGroup, industry, items: [] }
        }
        groups[groupKey].items.push(item)
    }
    // 转为有序数组：按市场排序，行业内按 priority + 名字
    const marketOrder = { '🇨🇳 A股': 0, '🇭🇰 港股': 1, '🇺🇸 美股': 2 }
    return Object.values(groups).sort((a, b) => {
        const ma = marketOrder[a.market] ?? 9
        const mb = marketOrder[b.market] ?? 9
        if (ma !== mb) return ma - mb
        return a.industry.localeCompare(b.industry, 'zh')
    })
})

// 搜索股票建议（代码/名称/拼音首字母）
async function querySearch(q, cb) {
    if (!q || q.trim().length < 1) return cb([])
    try {
        const { data } = await searchStockInfo(q.trim())
        cb(data.results || [])
    } catch {
        cb([])
    }
}

function handleSelect(item) {
    form.value.code = item.code
    form.value.name = item.name
}

// ===== 多备注 =====
const stockNotes = ref([])
const showAddNoteInput = ref(false)
const newNoteText = ref('')

// ===== 提醒系统 =====
const stockReminders = ref([])
const showAddReminderInput = ref(false)
const reminderForm = ref({
    type: 'price',
    condition: 'above',
    priceValue: null,
    dateValue: null,
    noteText: '',
})
const canAddReminder = computed(() => {
    if (reminderForm.value.type === 'price') {
        return reminderForm.value.condition && reminderForm.value.priceValue > 0
    }
    return reminderForm.value.dateValue
})

function resetReminderForm() {
    reminderForm.value = { type: 'price', condition: 'above', priceValue: null, dateValue: null, noteText: '' }
}

// ===== 当前分析数据 =====
const profileData = ref(null)
const analyzing = ref(false)

// ===== 选中股票的历次分析记录 =====
const stockHistory = ref([])
const detailHist = ref(null)
const showDetailDialog = ref(false)

// 打开添加对话框时重置表单
watch(showAddDialog, (v) => {
    if (v) {
        form.value = { code: '', name: '', priority: 'medium', reason: '' }
        searchText.value = ''
    }
})

// ===== 观察池 =====
async function loadData() {
    try {
        const { data } = await getWatchlist()
        items.value = data.items || []
    } catch {
        ElMessage.error('加载观察池失败')
    }
}

function selectItem(item) {
    selected.value = item
    profileData.value = null
    stockHistory.value = []
    detailHist.value = null
    stockNotes.value = []
    stockReminders.value = []
    prediction.value = null
    showAddNoteInput.value = false
    newNoteText.value = ''

    // 加载当前分析 + 历次分析 + 备注 + 提醒
    loadProfile()
    loadStockHistory()
    loadNotes()
    loadReminders()
}

function pType(p) {
    return p === 'high' ? 'danger' : p === 'medium' ? 'warning' : 'info'
}
function pLabel(p) {
    return p === 'high' ? '高' : p === 'medium' ? '中' : '低'
}

async function handleAdd() {
    if (!form.value.code || !form.value.name) {
        ElMessage.warning('请填写代码和名称')
        return
    }
    adding.value = true
    try {
        await addWatchItem(form.value)
        ElMessage.success('添加成功')
        form.value = { code: '', name: '', priority: 'medium', reason: '' }
        showAddDialog.value = false
        await loadData()
    } catch (e) {
        ElMessage.error(e.response?.data?.detail || '添加失败')
    } finally {
        adding.value = false
    }
}

async function handleRemove(code) {
    try {
        await removeWatchItem(code)
        ElMessage.success('已移除')
        if (selected.value?.code === code) {
            selected.value = null
            profileData.value = null
            stockHistory.value = []
        }
        await loadData()
    } catch {
        ElMessage.error('移除失败')
    }
}

function goAnalysis() {
    if (!selected.value?.code) return
    router.push({ path: '/analysis', query: { code: selected.value.code } })
}

function goToHistoryAnalysis(rec) {
    if (!rec?.code) return
    router.push({ path: '/analysis', query: { code: rec.code } })
}

async function setPriority(prio) {
    if (!selected.value || selected.value.priority === prio) return
    try {
        await updateWatchItem(selected.value.code, prio)
        selected.value.priority = prio
        await loadData()
    } catch {
        ElMessage.error('更新失败')
    }
}

// ===== 多备注（从 stock_notes API 获取） =====
async function loadNotes() {
    if (!selected.value?.code) { stockNotes.value = []; return }
    // 如果 profile 已经加载了 notes，直接用；否则单独查询
    if (profileData.value?.notes?.length) {
        stockNotes.value = profileData.value.notes
        return
    }
    try {
        const { data } = await getStockProfile(selected.value.code)
        stockNotes.value = data.notes || []
    } catch { stockNotes.value = [] }
}
async function handleAddNote() {
    if (!selected.value?.code || !newNoteText.value.trim()) return
    try {
        await addStockNote(selected.value.code, newNoteText.value.trim())
        newNoteText.value = ''
        ElMessage.success('备注已添加')
        await loadNotes()
    } catch { ElMessage.error('添加备注失败') }
}
async function handleDeleteNote(note) {
    if (!selected.value?.code) return
    try {
        await deleteStockNote(selected.value.code, note.id)
        ElMessage.success('备注已删除')
        await loadNotes()
    } catch { ElMessage.error('删除备注失败') }
}

// ===== 提醒系统 =====
async function loadReminders() {
    if (!selected.value?.code) { stockReminders.value = []; return }
    try {
        const { data } = await getStockReminders(selected.value.code)
        stockReminders.value = data.reminders || []
    } catch { stockReminders.value = [] }
}
async function handleAddReminder() {
    if (!selected.value?.code) return
    const f = reminderForm.value
    let target_value = ''
    if (f.type === 'price') {
        target_value = String(f.priceValue)
    } else {
        target_value = f.dateValue
    }
    try {
        await addStockReminder(selected.value.code, {
            type: f.type,
            condition: f.condition,
            target_value,
            note_text: f.noteText,
        })
        ElMessage.success('提醒已创建')
        showAddReminderInput.value = false
        resetReminderForm()
        await loadReminders()
    } catch { ElMessage.error('创建提醒失败') }
}
async function handleDeleteReminder(r) {
    if (!selected.value?.code) return
    try {
        await deleteStockReminder(selected.value.code, r.id)
        ElMessage.success('提醒已删除')
        await loadReminders()
    } catch { ElMessage.error('删除提醒失败') }
}
async function handleToggleReminder(r) {
    if (!selected.value?.code) return
    try {
        await toggleStockReminder(selected.value.code, r.id)
        r.enabled = r.enabled ? 0 : 1
    } catch { ElMessage.error('操作失败') }
}

// ===== AI趋势预测 =====
const predicting = ref(false)
const prediction = ref(null)

async function handlePredict() {
    if (!selected.value?.code) return
    predicting.value = true
    prediction.value = null
    try {
        const { data } = await predictStockTrend(selected.value.code)
        prediction.value = data
    } catch (e) {
        ElMessage.error(e.response?.data?.detail || '预测失败')
    } finally {
        predicting.value = false
    }
}

// ===== 分析 =====
async function loadProfile() {
    if (!selected.value?.code) return
    analyzing.value = true
    profileData.value = null
    try {
        const { data } = await getStockProfile(selected.value.code)
        profileData.value = data
        // 从 profile 返回的 notes 填充备注列表
        if (data.notes) {
            stockNotes.value = data.notes
        }
        // profileData.analysis_history 里也包含历次记录，提取出来
        if (data.analysis_history?.length) {
            stockHistory.value = data.analysis_history
        }
    } catch {
        // 静默
    } finally {
        analyzing.value = false
    }
}

async function handleSaveSnapshot() {
    if (!selected.value?.code || !profileData.value) {
        ElMessage.warning('请先分析该股票')
        return
    }
    savingSnapshot.value = true
    try {
        const analysisData = {
            technical: profileData.value,
            fundamental: profileData.value,
            risk_check: { passed: profileData.value.risk_passed },
        }
        await saveSnapshot(selected.value.code, {
            name: selected.value.name,
            sector: profileData.value.sector || '',
            analysis_data: analysisData,
        })
        ElMessage.success('快照已保存')
        await loadStockHistory()
    } catch (e) {
        ElMessage.error(e.response?.data?.detail || '保存快照失败')
    } finally {
        savingSnapshot.value = false
    }
}

async function handleDeleteSnapshot(rec) {
    try {
        await deleteSnapshot(selected.value.code, rec.snapshot_id)
        ElMessage.success('快照已删除')
        stockHistory.value = stockHistory.value.filter(r => !(r.record_type === 'snapshot' && r.snapshot_id === rec.snapshot_id))
    } catch (e) {
        ElMessage.error(e.response?.data?.detail || '删除失败')
    }
}

async function handleDeleteDraft(rec) {
    try {
        await deleteDraft(selected.value.code, rec.analysis_date)
        ElMessage.success('草稿已删除')
        stockHistory.value = stockHistory.value.filter(r => !(r.record_type === 'draft' && r.analysis_date === rec.analysis_date && r.code === rec.code))
    } catch (e) {
        ElMessage.error(e.response?.data?.detail || '删除失败')
    }
}

async function refreshAnalysis() {
    if (!selected.value?.code) return
    analyzing.value = true
    try {
        const { data } = await getStockProfile(selected.value.code)
        profileData.value = data
        ElMessage.success('分析已完成')
        // 从profile结果中提取历次分析记录
        if (data.analysis_history?.length) {
            stockHistory.value = data.analysis_history
        } else {
            await loadStockHistory()
        }
    } catch {
        ElMessage.error('分析失败')
    } finally {
        analyzing.value = false
    }
}

// ===== 趋势状态判断（5级：多头/偏多/偏空/空头/震荡）=====
function getTrendStatus(rec) {
    // 优先使用后端返回的 trend_status
    if (rec.trend_status && ['多头','偏多','偏空','空头','震荡'].includes(rec.trend_status)) {
        return rec.trend_status
    }
    // 兜底：从已有MA数据计算
    const { ma5, ma10, ma20, ma60, price } = rec
    if (ma5 == null || ma10 == null || ma20 == null || ma60 == null) return '震荡'
    if (ma5 > ma10 && ma10 > ma20 && ma20 > ma60) return '多头'
    if (ma5 < ma10 && ma10 < ma20 && ma20 < ma60) return '空头'
    if (ma5 > ma20 && price > ma60) return '偏多'
    if (ma5 < ma20 && price < ma60) return '偏空'
    return '震荡'
}

function detailTagType(rec) {
    const s = getTrendStatus(rec)
    if (s === '多头') return 'success'
    if (s === '偏多') return 'warning'
    if (s === '偏空') return 'danger'
    if (s === '空头') return 'danger'
    return 'info'
}
function detailTagLabel(rec) {
    const s = getTrendStatus(rec)
    const map = { '多头': '📈 均线多头', '偏多': '📈 均线偏多', '偏空': '📉 均线偏空', '空头': '📉 均线空头', '震荡': '〰️ 均线震荡' }
    return map[s] || '〰️ 均线震荡'
}

// ===== 历次分析记录（从 profile API 的 analysis_history 提取） =====
async function loadStockHistory() {
    if (!selected.value?.code) return
    // 如果已经有 profileData 且有 analysis_history，直接用
    if (profileData.value?.analysis_history?.length) {
        stockHistory.value = profileData.value.analysis_history
        return
    }
    // 否则重新请求 profile
    try {
        const { data } = await getStockProfile(selected.value.code)
        if (data.analysis_history?.length) {
            stockHistory.value = data.analysis_history
        }
    } catch {
        // 静默
    }
}

function showDetail(rec) {
    detailHist.value = rec
    showDetailDialog.value = true
}

const detailTitle = computed(() => {
    if (!detailHist.value) return '分析详情'
    return `📋 ${detailHist.value.name} (${detailHist.value.code}) — ${detailHist.value.analysis_date}`
})
</script>

<style scoped>
.watchlist-page { max-width: 1500px; margin: 0 auto; }
.panel-list { min-height: 500px; }
.panel-history { min-height: 500px; }

.scroll-area {
    max-height: 620px; overflow-y: auto;
}

/* 观察池列表 */
.watch-item {
    padding: 10px 8px;
    border-bottom: 1px solid #f0f0f0;
    cursor: pointer;
    border-left: 3px solid transparent;
    transition: background 0.2s;
}
.watch-item:hover { background: #f5f7fa; }
.watch-item.priority-high { border-left-color: #f56c6c; }
.watch-item.priority-medium { border-left-color: #e6a23c; }
.watch-item.priority-low { border-left-color: #909399; }
.watch-code { font-size: 13px; font-weight: bold; color: #303133; display: flex; align-items: center; }
.watch-name { font-size: 12px; color: #606266; margin-top: 2px; }
.watch-sector { font-size: 11px; color: #909399; margin-top: 1px; }

/* 历次分析列表 */
.history-item {
    padding: 10px 8px;
    border-bottom: 1px solid #f0f0f0;
    cursor: pointer;
    transition: background 0.15s;
    border-left: 3px solid transparent;
}
.history-item:hover { background: #f5f7fa; border-left-color: #409eff; }
.history-active {
    background: #ecf5ff;
    border-left-color: #409eff;
}
.history-header {
    display: flex; align-items: center; gap: 4px;
    font-size: 12px; margin-bottom: 4px;
}
.history-date {
    margin-left: auto;
    color: #909399;
    font-size: 11px;
}
.history-meta {
    display: flex; align-items: center; gap: 8px;
    font-size: 11px; color: #606266; flex-wrap: wrap;
}

/* 备注时间线 */
.note-timeline {
    max-height: 280px; overflow-y: auto;
}
.note-item {
    display: flex; gap: 10px; padding: 8px 0;
    border-bottom: 1px solid #f0f0f0;
}
.note-item:last-child { border-bottom: none; }
.note-dot {
    width: 8px; height: 8px; border-radius: 50%;
    background: #409eff; margin-top: 6px; flex-shrink: 0;
}
.note-body { flex: 1; min-width: 0; }
.note-meta {
    display: flex; align-items: center; gap: 8px; margin-bottom: 4px;
}
.note-date { color: #909399; font-size: 11px; }
.note-text {
    font-size: 13px; color: #303133;
    line-height: 1.6; white-space: pre-wrap; word-break: break-all;
}

/* 提醒列表 */
.reminder-list { max-height: 300px; overflow-y: auto; }
.reminder-item {
    display: flex; gap: 10px; padding: 8px 0;
    border-bottom: 1px solid #f0f0f0;
}
.reminder-item:last-child { border-bottom: none; }
.reminder-item.reminder-triggered { opacity: 0.6; }
.reminder-item.reminder-disabled { opacity: 0.5; }
.reminder-icon { flex-shrink: 0; }
.reminder-body { flex: 1; min-width: 0; }
.reminder-target { font-size: 13px; margin-bottom: 2px; }
.reminder-note { font-size: 12px; color: #606266; margin-bottom: 2px; }
.reminder-meta {
    display: flex; align-items: center; gap: 4px; margin-top: 4px;
}
.reminder-date { color: #909399; font-size: 11px; }
</style>
