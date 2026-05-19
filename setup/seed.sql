-- ============================================================
-- AI投研助手 - 数据库种子文件
-- 包含：完整表结构 + 个股基本信息(12371条) + 初始配置数据
-- 用法: sqlite3 ~/Jarvis/ai_trading/stock_archive.db < seed.sql
-- ============================================================

     1|CREATE TABLE stock_notes (
     2|            id INTEGER PRIMARY KEY AUTOINCREMENT,
     3|            code TEXT NOT NULL,
     4|            note TEXT NOT NULL,
     5|            created_at TEXT DEFAULT (datetime('now', 'localtime'))
     6|        );
     7|CREATE TABLE sqlite_sequence(name,seq);
     8|CREATE TABLE watchlist (
     9|            code TEXT PRIMARY KEY NOT NULL,
    10|            name TEXT NOT NULL,
    11|            sector TEXT,
    12|            reason TEXT DEFAULT '',
    13|            priority TEXT DEFAULT 'medium' CHECK(priority IN ('high','medium','low')),
    14|            added_date TEXT DEFAULT (date('now','localtime')),
    15|            last_analysis_date TEXT,
    16|            notes TEXT DEFAULT '',
    17|            created_at TEXT DEFAULT (datetime('now', 'localtime'))
    18|        );
    19|CREATE TABLE kline_daily (
    20|            code TEXT NOT NULL,
    21|            date TEXT NOT NULL,
    22|            open REAL,
    23|            close REAL,
    24|            high REAL,
    25|            low REAL,
    26|            volume REAL,
    27|            PRIMARY KEY (code, date)
    28|        );
    29|CREATE TABLE chat_history (
    30|            id INTEGER PRIMARY KEY AUTOINCREMENT,
    31|            code TEXT NOT NULL,
    32|            role TEXT NOT NULL CHECK(role IN ('user', 'assistant')),
    33|            content TEXT NOT NULL,
    34|            stock_name TEXT DEFAULT '',
    35|            created_at TEXT DEFAULT (datetime('now', 'localtime'))
    36|        );
    37|CREATE TABLE ai_analysis (
    38|            id INTEGER PRIMARY KEY AUTOINCREMENT,
    39|            code TEXT NOT NULL,
    40|            name TEXT DEFAULT '',
    41|            summary TEXT NOT NULL,
    42|            chat_count INTEGER DEFAULT 0,
    43|            created_at TEXT DEFAULT (datetime('now', 'localtime'))
    44|        );
    45|CREATE TABLE financial_reports (
    46|            code TEXT NOT NULL,
    47|            period TEXT NOT NULL,
    48|            revenue TEXT,
    49|            revenue_yoy TEXT,
    50|            net_profit TEXT,
    51|            net_profit_yoy TEXT,
    52|            gross_margin TEXT,
    53|            net_margin TEXT,
    54|            eps TEXT,
    55|            bps TEXT,
    56|            roe TEXT,
    57|            debt_ratio TEXT,
    58|            current_ratio TEXT,
    59|            fetched_at TEXT DEFAULT (datetime('now', 'localtime')),
    60|            PRIMARY KEY (code, period)
    61|        );
    62|CREATE TABLE stock_info (
    63|            code TEXT PRIMARY KEY,
    64|            name TEXT NOT NULL,
    65|            market TEXT DEFAULT '',
    66|            concepts TEXT DEFAULT '[]',
    67|            industry TEXT DEFAULT '',
    68|            total_shares REAL,
    69|            circulating_shares REAL,
    70|            total_market_cap REAL,
    71|            circulating_market_cap REAL,
    72|            listing_date TEXT DEFAULT '',
    73|            pinyin_initials TEXT DEFAULT '',
    74|            pinyin_full TEXT DEFAULT '',
    75|            data_source TEXT DEFAULT 'csv',
    76|            last_updated TEXT DEFAULT (datetime('now','localtime'))
    77|        );
    78|CREATE TABLE risk_rules (
    79|            id INTEGER PRIMARY KEY AUTOINCREMENT,
    80|            name TEXT NOT NULL,
    81|            description TEXT DEFAULT '',
    82|            rule_type TEXT NOT NULL,
    83|            field TEXT NOT NULL,
    84|            operator TEXT NOT NULL,
    85|            value TEXT NOT NULL,
    86|            unit TEXT DEFAULT '',
    87|            severity TEXT DEFAULT 'fail',
    88|            custom_detail TEXT DEFAULT '',
    89|            enabled INTEGER DEFAULT 1,
    90|            sort_order INTEGER DEFAULT 0,
    91|            created_at TEXT DEFAULT (datetime('now','localtime')),
    92|            updated_at TEXT DEFAULT (datetime('now','localtime'))
    93|        );
    94|CREATE TABLE analysis_snapshots (
    95|            id INTEGER PRIMARY KEY AUTOINCREMENT,
    96|            code TEXT NOT NULL,
    97|            name TEXT NOT NULL,
    98|            sector TEXT,
    99|            analysis_date TEXT NOT NULL,
   100|            created_at TEXT DEFAULT (datetime('now', 'localtime')),
   101|            price REAL, change_pct REAL,
   102|            ma5 REAL, ma10 REAL, ma20 REAL, ma60 REAL, ma200 REAL,
   103|            rsi14 REAL,
   104|            macd_dif REAL, macd_dea REAL, macd_hist REAL,
   105|            bullish_alignment INTEGER DEFAULT 0,
   106|            risk_passed INTEGER DEFAULT 0,
   107|            revenue TEXT, net_profit TEXT, gross_margin REAL, roe REAL
   108|        , snapshot_notes TEXT DEFAULT '', analysis_json TEXT DEFAULT '');
   109|CREATE TABLE financial_cache (
   110|            code TEXT PRIMARY KEY,
   111|            data TEXT NOT NULL,
   112|            created_at TEXT DEFAULT (datetime('now','localtime'))
   113|        );
   114|CREATE TABLE industry_chain (
   115|            industry TEXT PRIMARY KEY,
   116|            chain_data TEXT NOT NULL,
   117|            updated_at TEXT NOT NULL,
   118|            notes TEXT DEFAULT ''
   119|        );
   120|CREATE TABLE kg_articles (
   121|            id INTEGER PRIMARY KEY AUTOINCREMENT,
   122|            title TEXT NOT NULL DEFAULT '',
   123|            source TEXT DEFAULT 'text',
   124|            content TEXT NOT NULL,
   125|            entities TEXT DEFAULT '[]',
   126|            relations TEXT DEFAULT '[]',
   127|            created_at TEXT DEFAULT (datetime('now','localtime')),
   128|            updated_at TEXT DEFAULT (datetime('now','localtime'))
   129|        , summary TEXT DEFAULT '');
   130|CREATE TABLE kg_entity_stats (
   131|            name TEXT PRIMARY KEY,
   132|            category TEXT DEFAULT '',
   133|            count INTEGER DEFAULT 1,
   134|            last_seen TEXT DEFAULT (datetime('now','localtime'))
   135|        , entity_type TEXT DEFAULT '');
   136|CREATE TABLE kg_relation_stats (
   137|            source TEXT,
   138|            target TEXT,
   139|            relation TEXT,
   140|            count INTEGER DEFAULT 1,
   141|            PRIMARY KEY (source, target, relation)
   142|        );
   143|CREATE TABLE mental_models (
   144|            id INTEGER PRIMARY KEY AUTOINCREMENT,
   145|            name TEXT NOT NULL UNIQUE,
   146|            icon TEXT DEFAULT '',
   147|            category TEXT NOT NULL,
   148|            description TEXT NOT NULL,
   149|            application TEXT DEFAULT '',
   150|            scenario TEXT DEFAULT '',
   151|            example TEXT DEFAULT '',
   152|            detail TEXT DEFAULT '',
   153|            tags TEXT DEFAULT '[]',
   154|            created_at TEXT DEFAULT (datetime('now','localtime'))
   155|        );
   156|CREATE TABLE sector_dispersion (
   157|            id INTEGER PRIMARY KEY AUTOINCREMENT,
   158|            date TEXT NOT NULL,
   159|            sector TEXT NOT NULL,
   160|            avg_change REAL,
   161|            std_change REAL,
   162|            up_pct REAL,
   163|            stock_count INTEGER,
   164|            max_change REAL,
   165|            min_change REAL,
   166|            created_at TEXT DEFAULT (datetime('now','localtime'))
   167|        );
   168|CREATE TABLE model_trainings (
   169|            id INTEGER PRIMARY KEY AUTOINCREMENT,
   170|            model_name TEXT NOT NULL,
   171|            training_date TEXT NOT NULL,
   172|            market_context TEXT DEFAULT '',
   173|            training_answer TEXT DEFAULT '',
   174|            prediction TEXT DEFAULT '',
   175|            next_day_result TEXT DEFAULT '',
   176|            accuracy TEXT DEFAULT '',
   177|            market_context_date TEXT DEFAULT '',
   178|            reflection TEXT DEFAULT '',
   179|            created_at TEXT DEFAULT (datetime('now','localtime'))
   180|        , user_answer TEXT DEFAULT '', user_prediction TEXT DEFAULT '');
   181|CREATE TABLE sector_cycles (
   182|            id INTEGER PRIMARY KEY AUTOINCREMENT,
   183|            date TEXT NOT NULL,
   184|            sector TEXT NOT NULL,
   185|            avg_change REAL,
   186|            dispersion REAL,
   187|            up_pct REAL,
   188|            stock_count INTEGER,
   189|            max_change REAL,
   190|            min_change REAL,
   191|            phase TEXT NOT NULL,
   192|            icon TEXT DEFAULT '',
   193|            phase_order INTEGER DEFAULT 0,
   194|            created_at TEXT DEFAULT (datetime('now','localtime')),
   195|            UNIQUE(date, sector)
   196|        );
   197|CREATE INDEX idx_si_name ON stock_info(name);
   198|CREATE INDEX idx_si_pinyin ON stock_info(pinyin_initials);
   199|CREATE INDEX idx_rr_enabled ON risk_rules(enabled);
   200|CREATE INDEX idx_sd_date ON sector_dispersion(date);
   201|CREATE INDEX idx_mt_date ON model_trainings(training_date);
   202|CREATE INDEX idx_sc_date ON sector_cycles(date);
   203|CREATE INDEX idx_sc_sector ON sector_cycles(sector);
   204|CREATE TABLE sector_industry_cache (
   205|            id INTEGER PRIMARY KEY AUTOINCREMENT,
   206|            date TEXT NOT NULL,
   207|            sector TEXT NOT NULL,
   208|            rank INTEGER,
   209|            total_sectors INTEGER,
   210|            avg_change REAL,
   211|            up_ratio REAL,
   212|            stock_count INTEGER,
   213|            top_stocks TEXT DEFAULT '[]',
   214|            top_by_market_cap TEXT DEFAULT '[]',
   215|            updated_at TEXT DEFAULT (datetime('now','localtime')),
   216|            UNIQUE(date, sector)
   217|        );
   218|CREATE INDEX idx_sic_date ON sector_industry_cache(date);
   219|CREATE TABLE financial_data (
   220|            code TEXT,
   221|            report_period TEXT,
   222|            report_type TEXT,
   223|            data_json TEXT,
   224|            created_at TEXT DEFAULT (datetime('now','localtime')),
   225|            PRIMARY KEY (code, report_period, report_type)
   226|        );
   227|CREATE TABLE trade_logs (
   228|            id INTEGER PRIMARY KEY AUTOINCREMENT,
   229|            code TEXT NOT NULL,
   230|            direction TEXT NOT NULL CHECK(direction IN ('买入','卖出')),
   231|            trade_date TEXT NOT NULL,
   232|            quantity REAL NOT NULL,
   233|            price REAL NOT NULL,
   234|            total REAL NOT NULL,
   235|            note TEXT DEFAULT '',
   236|            created_at TEXT DEFAULT (datetime('now','localtime'))
   237|        );
   238|CREATE INDEX idx_tl_code ON trade_logs(code);
   239|CREATE TABLE sector_indices (
   240|            id INTEGER PRIMARY KEY AUTOINCREMENT,
   241|            date TEXT NOT NULL,
   242|            sector TEXT NOT NULL,
   243|            index_value REAL,
   244|            daily_return REAL,
   245|            total_mv REAL,
   246|            stock_count INTEGER,
   247|            updated_at TEXT DEFAULT (datetime('now','localtime')),
   248|            UNIQUE(date, sector)
   249|        );
   250|CREATE INDEX idx_si_date ON sector_indices(date);
   251|CREATE INDEX idx_si_sector ON sector_indices(sector);
   252|CREATE TABLE IF NOT EXISTS "stock_archive" (
   253|    code TEXT PRIMARY KEY,
   254|    name TEXT NOT NULL,
   255|    sector TEXT,
   256|    analysis_date TEXT NOT NULL,
   257|    price REAL, change_pct REAL,
   258|    pe REAL, pb REAL, market_cap REAL, turnover REAL,
   259|    ma5 REAL, ma10 REAL, ma20 REAL, ma60 REAL, ma200 REAL,
   260|    rsi14 REAL,
   261|    macd_dif REAL, macd_dea REAL, macd_hist REAL,
   262|    bullish_alignment INTEGER DEFAULT 0,
   263|    risk_passed INTEGER DEFAULT 0,
   264|    revenue TEXT, net_profit TEXT,
   265|    gross_margin REAL, roe REAL,
   266|    industry_rank INTEGER, industry_total INTEGER,
   267|    industry_avg_chg REAL,
   268|    notes TEXT DEFAULT '',
   269|    created_at TEXT DEFAULT (datetime('now', 'localtime')),
   270|    analysis_json TEXT DEFAULT ''
   271|);
   272|CREATE TABLE stock_reminders (
   273|            id INTEGER PRIMARY KEY AUTOINCREMENT,
   274|            code TEXT NOT NULL,
   275|            type TEXT NOT NULL CHECK(type IN ('price','time')),
   276|            condition TEXT NOT NULL CHECK(condition IN ('above','below','date')),
   277|            target_value TEXT NOT NULL,
   278|            note_text TEXT DEFAULT '',
   279|            enabled INTEGER DEFAULT 1,
   280|            triggered INTEGER DEFAULT 0,
   281|            created_at TEXT DEFAULT (datetime('now', 'localtime'))
   282|        );
   283|CREATE TABLE contradiction_ai_cache (
   284|            code TEXT NOT NULL,
   285|            report_period TEXT NOT NULL,
   286|            thinking_questions TEXT NOT NULL,
   287|            created_at TEXT DEFAULT (datetime('now', 'localtime')),
   288|            PRIMARY KEY (code, report_period)
   289|        );
   290|CREATE TABLE cron_history (
   291|            id INTEGER PRIMARY KEY AUTOINCREMENT,
   292|            task_name TEXT NOT NULL,
   293|            started_at TEXT NOT NULL,
   294|            finished_at TEXT,
   295|            status TEXT NOT NULL DEFAULT 'running',
   296|            message TEXT DEFAULT '',
   297|            created_at TEXT DEFAULT (datetime('now','localtime'))
   298|        );
   299|CREATE INDEX idx_cron_task ON cron_history(task_name);
   300|CREATE INDEX idx_cron_started ON cron_history(started_at);
   301|

-- ═══════════════════════════════════════════════════════════
-- 个股基本信息（12371条，从CSV导入）
-- ═══════════════════════════════════════════════════════════

BEGIN TRANSACTION;

     1|INSERT INTO "table" VALUES('000001','平安银行','深市','[]','银行Ⅱ',NULL,NULL,2229.6999999999997932,NULL,'','payh','','csv','2026-05-05 14:11:08');
     2|INSERT INTO "table" VALUES('000002','万  科Ａ','深市','[]','房地产开发',NULL,NULL,381.87999999999998834,NULL,'','w  kＡ','','csv','2026-05-05 14:11:08');
     3|INSERT INTO "table" VALUES('000003','PT金田A','深市','[]','--',NULL,NULL,5.2000000000000001776,NULL,'','PTjtA','','csv','2026-05-05 14:11:09');
     4|INSERT INTO "table" VALUES('000004','*ST国华','深市','[]','软件开发',NULL,NULL,3.4900000000000002131,NULL,'','*STgh','','csv','2026-05-05 14:11:09');
     5|INSERT INTO "table" VALUES('000005','ST星源','深市','[]','--',NULL,NULL,8.7799999999999993605,NULL,'','STxy','','csv','2026-05-05 14:11:09');
     6|INSERT INTO "table" VALUES('000006','深振业Ａ','深市','[]','房地产开发',NULL,NULL,129.86999999999999744,NULL,'','szyＡ','','csv','2026-05-05 14:11:10');
     7|INSERT INTO "table" VALUES('000007','全新好','深市','[]','一般零售',NULL,NULL,51.450000000000004618,NULL,'','qxh','','csv','2026-05-05 14:11:07');
     8|INSERT INTO "table" VALUES('000008','神州高铁','深市','[]','轨交设备Ⅱ',NULL,NULL,73.340000000000005186,NULL,'','szgt','','csv','2026-05-05 14:11:09');
     9|INSERT INTO "table" VALUES('000009','中国宝安','深市','[]','综合Ⅱ',NULL,NULL,222.56999999999997896,NULL,'','zgba','','csv','2026-05-05 14:11:09');
    10|INSERT INTO "table" VALUES('000010','*ST美丽','深市','[]','基础建设',NULL,NULL,25.089999999999998969,NULL,'','*STml','','csv','2026-05-05 14:11:13');
    11|INSERT INTO "table" VALUES('000011','深物业A','深市','[]','房地产开发',NULL,NULL,42.380000000000004334,NULL,'','swyA','','csv','2026-05-05 14:11:11');
    12|INSERT INTO "table" VALUES('000012','南  玻Ａ','深市','[]','玻璃玻纤',NULL,NULL,79.159999999999994813,NULL,'','n  bＡ','','csv','2026-05-05 14:11:13');
    13|INSERT INTO "table" VALUES('000013','*ST石化A','深市','[]','--',NULL,NULL,1.2700000000000000177,NULL,'','*STshA','','csv','2026-05-05 14:11:09');
    14|INSERT INTO "table" VALUES('000014','沙河股份','深市','[]','房地产开发',NULL,NULL,31.730000000000000426,NULL,'','shgf','','csv','2026-05-05 14:11:10');
    15|INSERT INTO "table" VALUES('000015','PT中浩A','深市','[]','--',NULL,NULL,1.8,NULL,'','PTzhA','','csv','2026-05-05 14:11:09');
    16|INSERT INTO "table" VALUES('000016','*ST康佳A','深市','[]','白色家电',NULL,NULL,51.730000000000000426,NULL,'','*STkjA','','csv','2026-05-05 14:11:08');
    17|INSERT INTO "table" VALUES('000017','深中华A','深市','[]','饰品',NULL,NULL,28.210000000000000852,NULL,'','szhA','','csv','2026-05-05 14:11:10');
    18|INSERT INTO "table" VALUES('000018','神城A退','深市','[]','--',NULL,NULL,2.6899999999999999467,NULL,'','scAt','','csv','2026-05-05 14:11:09');
    19|INSERT INTO "table" VALUES('000019','深粮控股','深市','[]','农产品加工',NULL,NULL,31.800000000000001598,NULL,'','slkg','','csv','2026-05-05 14:11:12');
    20|INSERT INTO "table" VALUES('000020','深华发Ａ','深市','[]','光学光电子',NULL,NULL,28.899999999999996802,NULL,'','shfＡ','','csv','2026-05-05 14:11:09');
    21|INSERT INTO "table" VALUES('000021','深科技','深市','[]','消费电子',NULL,NULL,458.83000000000002671,NULL,'','skj','','csv','2026-05-05 14:11:11');
    22|INSERT INTO "table" VALUES('000023','*ST深天','深市','[]','--',NULL,NULL,2.3799999999999998934,NULL,'','*STst','','csv','2026-05-05 14:11:09');
    23|INSERT INTO "table" VALUES('000024','招商地产','深市','[]','--',NULL,NULL,415.70000000000000284,NULL,'','zsdc','','csv','2026-05-05 14:11:09');
    24|INSERT INTO "table" VALUES('000025','特  力Ａ','深市','[]','综合Ⅱ',NULL,NULL,64.769999999999994244,NULL,'','t  lＡ','','csv','2026-05-05 14:11:07');
    25|INSERT INTO "table" VALUES('000026','飞亚达','深市','[]','饰品',NULL,NULL,65.80000000000000071,NULL,'','fyd','','csv','2026-05-05 14:11:11');
    26|INSERT INTO "table" VALUES('000027','深圳能源','深市','[]','电力',NULL,NULL,325.41000000000002145,NULL,'','szny','','csv','2026-05-05 14:11:09');
    27|INSERT INTO "table" VALUES('000028','国药一致','深市','[]','医药商业',NULL,NULL,117.21999999999999086,NULL,'','gyyz','','csv','2026-05-05 14:11:08');
    28|INSERT INTO "table" VALUES('000029','深深房Ａ','深市','[]','房地产开发',NULL,NULL,188.59000000000001762,NULL,'','ssfＡ','','csv','2026-05-05 14:11:10');
    29|INSERT INTO "table" VALUES('000030','富奥股份','深市','[]','汽车零部件',NULL,NULL,85.049999999999990052,NULL,'','fagf','','csv','2026-05-05 14:11:10');
    30|INSERT INTO "table" VALUES('000031','大悦城','深市','[]','房地产开发',NULL,NULL,132.44999999999997886,NULL,'','dyc','','csv','2026-05-05 14:11:10');
    31|INSERT INTO "table" VALUES('000032','深桑达Ａ','深市','[]','专业工程',NULL,NULL,189.77000000000002088,NULL,'','ssdＡ','','csv','2026-05-05 14:11:09');
    32|INSERT INTO "table" VALUES('000033','新都退','深市','[]','--',NULL,NULL,7.3099999999999996092,NULL,'','xdt','','csv','2026-05-05 14:11:09');
    33|INSERT INTO "table" VALUES('000034','神州数码','深市','[]','IT服务Ⅱ',NULL,NULL,230.400000000000027,NULL,'','szsm','','csv','2026-05-05 14:11:07');
    34|INSERT INTO "table" VALUES('000035','中国天楹','深市','[]','环境治理',NULL,NULL,150.80999999999999516,NULL,'','zgty','','csv','2026-05-05 14:11:10');
    35|INSERT INTO "table" VALUES('000036','华联控股','深市','[]','房地产开发',NULL,NULL,78.849999999999997868,NULL,'','hlkg','','csv','2026-05-05 14:11:11');
    36|INSERT INTO "table" VALUES('000037','深南电A','深市','[]','电力',NULL,NULL,36.670000000000002593,NULL,'','sndA','','csv','2026-05-05 14:11:11');
    37|INSERT INTO "table" VALUES('000038','大通退','深市','[]','--',NULL,NULL,1.3000000000000000444,NULL,'','dtt','','csv','2026-05-05 14:11:09');
    38|INSERT INTO "table" VALUES('000039','中集集团','深市','[]','通用设备',NULL,NULL,283.06999999999998607,NULL,'','zjjt','','csv','2026-05-05 14:11:07');
    39|INSERT INTO "table" VALUES('000040','*ST旭蓝','深市','[]','--',NULL,NULL,5.1699999999999999289,NULL,'','*STxl','','csv','2026-05-05 14:11:09');
    40|INSERT INTO "table" VALUES('000042','中洲控股','深市','[]','房地产开发',NULL,NULL,63.490000000000001989,NULL,'','zzkg','','csv','2026-05-05 14:11:08');
    41|INSERT INTO "table" VALUES('000045','深纺织Ａ','深市','[]','光学光电子',NULL,NULL,54.889999999999998792,NULL,'','sfzＡ','','csv','2026-05-05 14:11:10');
    42|INSERT INTO "table" VALUES('000046','*ST泛海','深市','[]','--',NULL,NULL,19.660000000000000142,NULL,'','*STfh','','csv','2026-05-05 14:11:09');
    43|INSERT INTO "table" VALUES('000047','ST中侨','深市','[]','--',NULL,NULL,2.6400000000000001243,NULL,'','STzq','','csv','2026-05-05 14:11:09');
    44|INSERT INTO "table" VALUES('000048','京基智农','深市','[]','养殖业',NULL,NULL,78.360000000000002984,NULL,'','jjzn','','csv','2026-05-05 14:11:07');
    45|INSERT INTO "table" VALUES('000049','德赛电池','深市','[]','电池',NULL,NULL,111.81999999999998607,NULL,'','dsdc','','csv','2026-05-05 14:11:10');
    46|INSERT INTO "table" VALUES('00005','汇丰控股','hk_stock','[]','港股',NULL,NULL,NULL,NULL,'','hfkg','','csv','2026-05-11 14:26:47');
    47|INSERT INTO "table" VALUES('000050','深天马Ａ','深市','[]','光学光电子',NULL,NULL,188.5099999999999909,NULL,'','stmＡ','','csv','2026-05-05 14:11:11');
    48|INSERT INTO "table" VALUES('000055','方大集团','深市','[]','装修建材',NULL,NULL,24.870000000000000994,NULL,'','fdjt','','csv','2026-05-05 14:11:07');
    49|INSERT INTO "table" VALUES('000056','*ST皇庭','深市','[]','房地产服务',NULL,NULL,15.720000000000000639,NULL,'','*STht','','csv','2026-05-05 14:11:12');
    50|INSERT INTO "table" VALUES('000058','深 赛 格','深市','[]','一般零售',NULL,NULL,80.650000000000012789,NULL,'','s s g','','csv','2026-05-05 14:11:09');
    51|INSERT INTO "table" VALUES('000059','华锦股份','深市','[]','炼化及贸易',NULL,NULL,91.17000000000000881,NULL,'','hjgf','','csv','2026-05-05 14:11:08');
    52|INSERT INTO "table" VALUES('000060','中金岭南','深市','[]','工业金属',NULL,NULL,298.88999999999995793,NULL,'','zjln','','csv','2026-05-05 14:11:11');
    53|INSERT INTO "table" VALUES('000061','农 产 品','深市','[]','一般零售',NULL,NULL,132.96000000000001151,NULL,'','n c p','','csv','2026-05-05 14:11:11');
    54|INSERT INTO "table" VALUES('000062','深圳华强','深市','[]','其他电子Ⅱ',NULL,NULL,391.83999999999997498,NULL,'','szhq','','csv','2026-05-05 14:11:12');
    55|INSERT INTO "table" VALUES('000063','中兴通讯','深市','[]','通信设备',NULL,NULL,1478.9400000000001433,NULL,'','zxtx','','csv','2026-05-05 14:11:12');
    56|INSERT INTO "table" VALUES('000065','北方国际','深市','[]','专业工程',NULL,NULL,124.31000000000000937,NULL,'','bfgj','','csv','2026-05-05 14:11:11');
    57|INSERT INTO "table" VALUES('000066','中国长城','深市','[]','计算机设备',NULL,NULL,639.29999999999997939,NULL,'','zgcc','','csv','2026-05-05 14:11:06');
    58|INSERT INTO "table" VALUES('000068','华控赛格','深市','[]','环境治理',NULL,NULL,32.920000000000002593,NULL,'','hksg','','csv','2026-05-05 14:11:12');
    59|INSERT INTO "table" VALUES('000069','华侨城Ａ','深市','[]','房地产开发',NULL,NULL,156.59999999999998365,NULL,'','hqcＡ','','csv','2026-05-05 14:11:09');
    60|INSERT INTO "table" VALUES('000070','特发信息','深市','[]','通信设备',NULL,NULL,164.66999999999998749,NULL,'','tfxx','','csv','2026-05-05 14:11:12');
    61|INSERT INTO "table" VALUES('000078','海王生物','深市','[]','医药商业',NULL,NULL,83.480000000000007531,NULL,'','hwsw','','csv','2026-05-05 14:11:07');
    62|INSERT INTO "table" VALUES('000088','盐 田 港','深市','[]','航运港口',NULL,NULL,142.95999999999999374,NULL,'','y t g','','csv','2026-05-05 14:11:07');
    63|INSERT INTO "table" VALUES('000089','深圳机场','深市','[]','航空机场',NULL,NULL,144.9900000000000233,NULL,'','szjc','','csv','2026-05-05 14:11:08');
    64|INSERT INTO "table" VALUES('000090','天健集团','深市','[]','房地产开发',NULL,NULL,65.95999999999999197,NULL,'','tjjt','','csv','2026-05-05 14:11:09');
    65|INSERT INTO "table" VALUES('000096','广聚能源','深市','[]','炼化及贸易',NULL,NULL,49.859999999999997655,NULL,'','gjny','','csv','2026-05-05 14:11:07');
    66|INSERT INTO "table" VALUES('000099','中信海直','深市','[]','航空机场',NULL,NULL,137.53999999999999559,NULL,'','zxhz','','csv','2026-05-05 14:11:08');
    67|INSERT INTO "table" VALUES('000100','TCL科技','深市','[]','光学光电子',NULL,NULL,826.50000000000005684,NULL,'','TCLkj','','csv','2026-05-05 14:11:09');
    68|INSERT INTO "table" VALUES('000150','*ST宜康','深市','[]','--',NULL,NULL,4.1100000000000003197,NULL,'','*STyk','','csv','2026-05-05 14:11:09');
    69|INSERT INTO "table" VALUES('000151','中成股份','深市','[]','贸易Ⅱ',NULL,NULL,36.610000000000000319,NULL,'','zcgf','','csv','2026-05-05 14:11:11');
    70|INSERT INTO "table" VALUES('000153','丰原药业','深市','[]','化学制药',NULL,NULL,29.729999999999998649,NULL,'','fyyy','','csv','2026-05-05 14:11:07');
    71|INSERT INTO "table" VALUES('000155','川能动力','深市','[]','电力',NULL,NULL,326.58999999999998031,NULL,'','cndl','','csv','2026-05-05 14:11:07');
    72|INSERT INTO "table" VALUES('000156','华数传媒','深市','[]','电视广播Ⅱ',NULL,NULL,126.29999999999999005,NULL,'','hscm','','csv','2026-05-05 14:11:10');
    73|INSERT INTO "table" VALUES('000157','中联重科','深市','[]','工程机械',NULL,NULL,563.45000000000000639,NULL,'','zlzk','','csv','2026-05-05 14:11:07');
    74|INSERT INTO "table" VALUES('000158','常山北明','深市','[]','IT服务Ⅱ',NULL,NULL,274.70999999999996532,NULL,'','csbm','','csv','2026-05-05 14:11:12');
    75|INSERT INTO "table" VALUES('000159','国际实业','深市','[]','炼化及贸易',NULL,NULL,31.14999999999999769,NULL,'','gjsy','','csv','2026-05-05 14:11:09');
    76|INSERT INTO "table" VALUES('00016','新鸿基地产','hk_stock','[]','港股',NULL,NULL,NULL,NULL,'','xhjdc','','csv','2026-05-11 14:26:47');
    77|INSERT INTO "table" VALUES('000166','申万宏源','深市','[]','证券Ⅱ',NULL,NULL,1072.6900000000001433,NULL,'','swhy','','csv','2026-05-05 14:11:07');
    78|INSERT INTO "table" VALUES('00020','商汤-W','hk_stock','[]','港股',NULL,NULL,NULL,NULL,'','st-W','','csv','2026-05-11 14:26:47');
    79|INSERT INTO "table" VALUES('00027','银河娱乐','hk_stock','[]','港股',NULL,NULL,NULL,NULL,'','yhyl','','csv','2026-05-11 14:26:47');
    80|INSERT INTO "table" VALUES('000301','东方盛虹','深市','[]','炼化及贸易',NULL,NULL,875.58000000000006934,NULL,'','dfsh','','csv','2026-05-05 14:11:07');
    81|INSERT INTO "table" VALUES('000333','美的集团','深市','[]','白色家电',NULL,NULL,5595.9399999999996921,NULL,'','mdjt','','csv','2026-05-05 14:11:07');
    82|INSERT INTO "table" VALUES('000338','潍柴动力','深市','[]','汽车零部件',NULL,NULL,1563.5899999999997689,NULL,'','wcdl','','csv','2026-05-05 14:11:07');
    83|INSERT INTO "table" VALUES('000400','许继电气','深市','[]','电网设备',NULL,NULL,254.84999999999997655,NULL,'','xjdq','','csv','2026-05-05 14:11:11');
    84|INSERT INTO "table" VALUES('000401','金隅冀东','深市','[]','水泥',NULL,NULL,113.67000000000000436,NULL,'','jyjd','','csv','2026-05-05 14:11:09');
    85|INSERT INTO "table" VALUES('000402','金 融 街','深市','[]','房地产开发',NULL,NULL,94.740000000000001989,NULL,'','j r j','','csv','2026-05-05 14:11:09');
    86|INSERT INTO "table" VALUES('000403','派林生物','深市','[]','生物制品',NULL,NULL,114.67000000000000525,NULL,'','plsw','','csv','2026-05-05 14:11:08');
    87|INSERT INTO "table" VALUES('000404','长虹华意','深市','[]','家电零部件Ⅱ',NULL,NULL,57.580000000000000071,NULL,'','chhy','','csv','2026-05-05 14:11:12');
    88|INSERT INTO "table" VALUES('000405','ST鑫光','深市','[]','--',NULL,NULL,3.2299999999999999822,NULL,'','STxg','','csv','2026-05-05 14:11:09');
    89|INSERT INTO "table" VALUES('000406','石油大明','深市','[]','--',NULL,NULL,26.899999999999999467,NULL,'','sydm','','csv','2026-05-05 14:11:09');
    90|INSERT INTO "table" VALUES('000407','胜利股份','深市','[]','燃气Ⅱ',NULL,NULL,42.740000000000000213,NULL,'','slgf','','csv','2026-05-05 14:11:07');
    91|INSERT INTO "table" VALUES('000408','藏格矿业','深市','[]','农化制品',NULL,NULL,1410.680000000000156,NULL,'','cgky','','csv','2026-05-05 14:11:10');
    92|INSERT INTO "table" VALUES('000409','云鼎科技','深市','[]','IT服务Ⅱ',NULL,NULL,60.049999999999998934,NULL,'','ydkj','','csv','2026-05-05 14:11:11');
    93|INSERT INTO "table" VALUES('000410','沈阳机床','深市','[]','通用设备',NULL,NULL,122.59999999999999786,NULL,'','syjc','','csv','2026-05-05 14:11:09');
    94|INSERT INTO "table" VALUES('000411','英特集团','深市','[]','医药商业',NULL,NULL,59.870000000000000994,NULL,'','ytjt','','csv','2026-05-05 14:11:12');
    95|INSERT INTO "table" VALUES('000412','ST五环','深市','[]','--',NULL,NULL,3.0699999999999998401,NULL,'','STwh','','csv','2026-05-05 14:11:09');
    96|INSERT INTO "table" VALUES('000413','ST旭电','深市','[]','--',NULL,NULL,18.609999999999999431,NULL,'','STxd','','csv','2026-05-05 14:11:09');
    97|INSERT INTO "table" VALUES('000415','渤海租赁','深市','[]','多元金融',NULL,NULL,255.08000000000001783,NULL,'','bhzl','','csv','2026-05-05 14:11:07');
    98|INSERT INTO "table" VALUES('000416','*ST民控','深市','[]','--',NULL,NULL,2.3900000000000001243,NULL,'','*STmk','','csv','2026-05-05 14:11:09');
    99|INSERT INTO "table" VALUES('000417','合百集团','深市','[]','一般零售',NULL,NULL,51.490000000000000213,NULL,'','hbjt','','csv','2026-05-05 14:11:10');
   100|INSERT INTO "table" VALUES('000418','小天鹅A','深市','[]','--',NULL,NULL,252.13999999999998635,NULL,'','xteA','','csv','2026-05-05 14:11:09');
   101|INSERT INTO "table" VALUES('000419','通程控股','深市','[]','一般零售',NULL,NULL,31.850000000000000532,NULL,'','tckg','','csv','2026-05-05 14:11:09');
   102|INSERT INTO "table" VALUES('000420','吉林化纤','深市','[]','化学纤维',NULL,NULL,125.11000000000001008,NULL,'','jlhx','','csv','2026-05-05 14:11:08');
   103|INSERT INTO "table" VALUES('000421','南京公用','深市','[]','综合Ⅱ',NULL,NULL,36.530000000000000248,NULL,'','njgy','','csv','2026-05-05 14:11:06');
   104|INSERT INTO "table" VALUES('000422','湖北宜化','深市','[]','农化制品',NULL,NULL,178.78000000000000113,NULL,'','hbyh','','csv','2026-05-05 14:11:07');
   105|INSERT INTO "table" VALUES('000423','东阿阿胶','深市','[]','中药Ⅱ',NULL,NULL,354.4700000000000184,NULL,'','deej','','csv','2026-05-05 14:11:07');
   106|INSERT INTO "table" VALUES('000425','徐工机械','深市','[]','工程机械',NULL,NULL,901.8200000000000216,NULL,'','xgjx','','csv','2026-05-05 14:11:07');
   107|INSERT INTO "table" VALUES('000426','兴业银锡','深市','[]','贵金属',NULL,NULL,758.37000000000003296,NULL,'','xyyx','','csv','2026-05-05 14:11:09');
   108|INSERT INTO "table" VALUES('000428','华天酒店','深市','[]','酒店餐饮',NULL,NULL,39.740000000000001989,NULL,'','htjd','','csv','2026-05-05 14:11:09');
   109|INSERT INTO "table" VALUES('000429','粤高速Ａ','深市','[]','铁路公路',NULL,NULL,161.47999999999997911,NULL,'','ygsＡ','','csv','2026-05-05 14:11:07');
   110|INSERT INTO "table" VALUES('000430','ST张家界','深市','[]','旅游及景区',NULL,NULL,29.089999999999998081,NULL,'','STzjj','','csv','2026-05-05 14:11:10');
   111|INSERT INTO "table" VALUES('000488','ST晨鸣','深市','[]','造纸',NULL,NULL,43.200000000000002842,NULL,'','STcm','','csv','2026-05-05 14:11:12');
   112|INSERT INTO "table" VALUES('000498','山东路桥','深市','[]','基础建设',NULL,NULL,80.440000000000004831,NULL,'','sdlq','','csv','2026-05-05 14:11:07');
   113|INSERT INTO "table" VALUES('000501','武商集团','深市','[]','一般零售',NULL,NULL,64.530000000000002913,NULL,'','wsjt','','csv','2026-05-05 14:11:09');
   114|INSERT INTO "table" VALUES('000502','绿景退','深市','[]','--',NULL,NULL,1.080000000000000071,NULL,'','ljt','','csv','2026-05-05 14:11:09');
   115|INSERT INTO "table" VALUES('000503','国新健康','深市','[]','软件开发',NULL,NULL,78.049999999999997157,NULL,'','gxjk','','csv','2026-05-05 14:11:09');
   116|INSERT INTO "table" VALUES('000504','*ST生物','深市','[]','医疗服务',NULL,NULL,30.249999999999999111,NULL,'','*STsw','','csv','2026-05-05 14:11:09');
   117|INSERT INTO "table" VALUES('000505','京粮控股','深市','[]','农产品加工',NULL,NULL,41.799999999999997157,NULL,'','jlkg','','csv','2026-05-05 14:11:10');
   118|INSERT INTO "table" VALUES('000506','招金黄金','深市','[]','贵金属',NULL,NULL,147.75999999999998024,NULL,'','zjhj','','csv','2026-05-05 14:11:12');
   119|INSERT INTO "table" VALUES('000507','珠海港','深市','[]','电力',NULL,NULL,46.740000000000003765,NULL,'','zhg','','csv','2026-05-05 14:11:08');
   120|INSERT INTO "table" VALUES('000508','琼民源A','深市','[]','--',NULL,NULL,44.030000000000004689,NULL,'','qmyA','','csv','2026-05-05 14:11:09');
   121|INSERT INTO "table" VALUES('000509','华塑控股','深市','[]','光学光电子',NULL,NULL,38.420000000000001705,NULL,'','hskg','','csv','2026-05-05 14:11:09');
   122|INSERT INTO "table" VALUES('000510','新金路','深市','[]','化学原料',NULL,NULL,85.229999999999996873,NULL,'','xjl','','csv','2026-05-05 14:11:07');
   123|INSERT INTO "table" VALUES('000511','烯碳退','深市','[]','--',NULL,NULL,7.0400000000000000355,NULL,'','xtt','','csv','2026-05-05 14:11:09');
   124|INSERT INTO "table" VALUES('000513','丽珠集团','深市','[]','化学制药',NULL,NULL,185.71999999999999175,NULL,'','lzjt','','csv','2026-05-05 14:11:08');
   125|INSERT INTO "table" VALUES('000514','渝 开 发','深市','[]','房地产开发',NULL,NULL,41.680000000000001492,NULL,'','y k f','','csv','2026-05-05 14:11:10');
   126|INSERT INTO "table" VALUES('000515','攀渝钛业','深市','[]','--',NULL,NULL,17.510000000000001563,NULL,'','pyty','','csv','2026-05-05 14:11:09');
   127|INSERT INTO "table" VALUES('000516','国际医学','深市','[]','医疗服务',NULL,NULL,101.37000000000000454,NULL,'','gjyx','','csv','2026-05-05 14:11:08');
   128|INSERT INTO "table" VALUES('000517','荣安地产','深市','[]','房地产开发',NULL,NULL,50.09000000000000341,NULL,'','radc','','csv','2026-05-05 14:11:07');
   129|INSERT INTO "table" VALUES('000518','*ST四环','深市','[]','生物制品',NULL,NULL,29.75,NULL,'','*STsh','','csv','2026-05-05 14:11:10');
   130|INSERT INTO "table" VALUES('000519','中兵红箭','深市','[]','地面兵装Ⅱ',NULL,NULL,246.19999999999997442,NULL,'','zbhj','','csv','2026-05-05 14:11:09');
   131|INSERT INTO "table" VALUES('000520','凤凰航运','深市','[]','航运港口',NULL,NULL,39.979999999999996873,NULL,'','fhhy','','csv','2026-05-05 14:11:07');
   132|INSERT INTO "table" VALUES('000521','长虹美菱','深市','[]','白色家电',NULL,NULL,49.640000000000004121,NULL,'','chml','','csv','2026-05-05 14:11:09');
   133|INSERT INTO "table" VALUES('000522','白云山A','深市','[]','--',NULL,NULL,109.15000000000001278,NULL,'','bysA','','csv','2026-05-05 14:11:09');
   134|INSERT INTO "table" VALUES('000523','红棉股份','深市','[]','综合Ⅱ',NULL,NULL,45.720000000000000639,NULL,'','hmgf','','csv','2026-05-05 14:11:07');
   135|INSERT INTO "table" VALUES('000524','岭南控股','深市','[]','旅游及景区',NULL,NULL,68.46999999999999531,NULL,'','lnkg','','csv','2026-05-05 14:11:07');
   136|INSERT INTO "table" VALUES('000525','红太阳','深市','[]','农化制品',NULL,NULL,62.259999999999999786,NULL,'','hty','','csv','2026-05-05 14:11:12');
   137|INSERT INTO "table" VALUES('000526','学大教育','深市','[]','教育',NULL,NULL,41.869999999999993889,NULL,'','xdjy','','csv','2026-05-05 14:11:13');
   138|INSERT INTO "table" VALUES('000527','美的电器','深市','[]','--',NULL,NULL,474.49000000000003396,NULL,'','mddq','','csv','2026-05-05 14:11:09');
   139|INSERT INTO "table" VALUES('000528','柳    工','深市','[]','工程机械',NULL,NULL,195.87999999999999189,NULL,'','l    g','','csv','2026-05-05 14:11:07');
   140|INSERT INTO "table" VALUES('000529','广弘控股','深市','[]','食品加工',NULL,NULL,32.310000000000003161,NULL,'','ghkg','','csv','2026-05-05 14:11:08');
   141|INSERT INTO "table" VALUES('000530','冰山冷热','深市','[]','通用设备',NULL,NULL,35.590000000000001634,NULL,'','bslr','','csv','2026-05-05 14:11:10');
   142|INSERT INTO "table" VALUES('000531','穗恒运Ａ','深市','[]','电力',NULL,NULL,64.230000000000000426,NULL,'','shyＡ','','csv','2026-05-05 14:11:07');
   143|INSERT INTO "table" VALUES('000532','华金资本','深市','[]','多元金融',NULL,NULL,43.559999999999998721,NULL,'','hjzb','','csv','2026-05-05 14:11:09');
   144|INSERT INTO "table" VALUES('000533','顺钠股份','深市','[]','电网设备',NULL,NULL,86.639999999999997015,NULL,'','sngf','','csv','2026-05-05 14:11:08');
   145|INSERT INTO "table" VALUES('000534','万泽股份','深市','[]','生物制品',NULL,NULL,198.58999999999999985,NULL,'','wzgf','','csv','2026-05-05 14:11:13');
   146|INSERT INTO "table" VALUES('000535','*ST猴王','深市','[]','--',NULL,NULL,0.85,NULL,'','*SThw','','csv','2026-05-05 14:11:09');
   147|INSERT INTO "table" VALUES('000536','华映科技','深市','[]','光学光电子',NULL,NULL,109.68999999999999772,NULL,'','hykj','','csv','2026-05-05 14:11:08');
   148|INSERT INTO "table" VALUES('000537','绿发电力','深市','[]','电力',NULL,NULL,203.92999999999998905,NULL,'','lfdl','','csv','2026-05-05 14:11:12');
   149|INSERT INTO "table" VALUES('000538','云南白药','深市','[]','中药Ⅱ',NULL,NULL,940.89999999999989199,NULL,'','ynby','','csv','2026-05-05 14:11:07');
   150|INSERT INTO "table" VALUES('000539','粤电力Ａ','深市','[]','电力',NULL,NULL,169.68000000000000859,NULL,'','ydlＡ','','csv','2026-05-05 14:11:06');
   151|INSERT INTO "table" VALUES('000540','*ST中天','深市','[]','--',NULL,NULL,27.890000000000001456,NULL,'','*STzt','','csv','2026-05-05 14:11:09');
   152|INSERT INTO "table" VALUES('000541','佛山照明','深市','[]','照明设备Ⅱ',NULL,NULL,69.519999999999999573,NULL,'','fszm','','csv','2026-05-05 14:11:11');
   153|INSERT INTO "table" VALUES('000542','TCL通讯','深市','[]','--',NULL,NULL,22.259999999999999786,NULL,'','TCLtx','','csv','2026-05-05 14:11:09');
   154|INSERT INTO "table" VALUES('000543','皖能电力','深市','[]','电力',NULL,NULL,182.93999999999998706,NULL,'','wndl','','csv','2026-05-05 14:11:08');
   155|INSERT INTO "table" VALUES('000544','中原环保','深市','[]','环境治理',NULL,NULL,82.260000000000008668,NULL,'','zyhb','','csv','2026-05-05 14:11:09');
   156|INSERT INTO "table" VALUES('000545','金浦钛业','深市','[]','化学原料',NULL,NULL,29.460000000000000852,NULL,'','jpty','','csv','2026-05-05 14:11:08');
   157|INSERT INTO "table" VALUES('000546','金圆股份','深市','[]','环境治理',NULL,NULL,53.719999999999998863,NULL,'','jygf','','csv','2026-05-05 14:11:10');
   158|INSERT INTO "table" VALUES('000547','航天发展','深市','[]','军工电子Ⅱ',NULL,NULL,388.37999999999999189,NULL,'','htfz','','csv','2026-05-05 14:11:13');
   159|INSERT INTO "table" VALUES('000548','湖南投资','深市','[]','铁路公路',NULL,NULL,26.760000000000001563,NULL,'','hntz','','csv','2026-05-05 14:11:08');
   160|INSERT INTO "table" VALUES('000549','S湘火炬','深市','[]','--',NULL,NULL,55.09000000000000341,NULL,'','Sxhj','','csv','2026-05-05 14:11:09');
   161|INSERT INTO "table" VALUES('000550','江铃汽车','深市','[]','商用车',NULL,NULL,97.829999999999994741,NULL,'','jlqc','','csv','2026-05-05 14:11:12');
   162|INSERT INTO "table" VALUES('000551','创元科技','深市','[]','环保设备Ⅱ',NULL,NULL,78.790000000000004476,NULL,'','cykj','','csv','2026-05-05 14:11:10');
   163|INSERT INTO "table" VALUES('000552','甘肃能化','深市','[]','煤炭开采',NULL,NULL,107.29999999999999538,NULL,'','gsnh','','csv','2026-05-05 14:11:07');
   164|INSERT INTO "table" VALUES('000553','安道麦A','深市','[]','农化制品',NULL,NULL,148.47999999999998976,NULL,'','admA','','csv','2026-05-05 14:11:08');
   165|INSERT INTO "table" VALUES('000554','泰山石油','深市','[]','炼化及贸易',NULL,NULL,29.670000000000001705,NULL,'','tssy','','csv','2026-05-05 14:11:09');
   166|INSERT INTO "table" VALUES('000555','神州信息','深市','[]','IT服务Ⅱ',NULL,NULL,134.11000000000001808,NULL,'','szxx','','csv','2026-05-05 14:11:13');
   167|INSERT INTO "table" VALUES('000556','PT南洋','深市','[]','--',NULL,NULL,1.7599999999999999644,NULL,'','PTny','','csv','2026-05-05 14:11:09');
   168|INSERT INTO "table" VALUES('000557','西部创业','深市','[]','铁路公路',NULL,NULL,68.519999999999994244,NULL,'','xbcy','','csv','2026-05-05 14:11:08');
   169|INSERT INTO "table" VALUES('000558','天府文旅','深市','[]','旅游及景区',NULL,NULL,54.640000000000004121,NULL,'','tfwl','','csv','2026-05-05 14:11:12');
   170|INSERT INTO "table" VALUES('000559','万向钱潮','深市','[]','汽车零部件',NULL,NULL,535.59999999999998721,NULL,'','wxqc','','csv','2026-05-05 14:11:13');
   171|INSERT INTO "table" VALUES('000560','我爱我家','深市','[]','房地产服务',NULL,NULL,69.450000000000002842,NULL,'','wawj','','csv','2026-05-05 14:11:09');
   172|INSERT INTO "table" VALUES('000561','烽火电子','深市','[]','航空装备Ⅱ',NULL,NULL,73.669999999999999928,NULL,'','fhdz','','csv','2026-05-05 14:11:11');
   173|INSERT INTO "table" VALUES('000562','宏源证券','深市','[]','--',NULL,NULL,1073.1400000000002048,NULL,'','hyzq','','csv','2026-05-05 14:11:09');
   174|INSERT INTO "table" VALUES('000563','陕国投Ａ','深市','[]','多元金融',NULL,NULL,166.72000000000000596,NULL,'','sgtＡ','','csv','2026-05-05 14:11:08');
   175|INSERT INTO "table" VALUES('000564','供销大集','深市','[]','一般零售',NULL,NULL,265.67000000000002835,NULL,'','gxdj','','csv','2026-05-05 14:11:10');
   176|INSERT INTO "table" VALUES('000565','渝三峡Ａ','深市','[]','化学制品',NULL,NULL,34.380000000000001669,NULL,'','ysxＡ','','csv','2026-05-05 14:11:09');
   177|INSERT INTO "table" VALUES('000566','海南海药','深市','[]','化学制药',NULL,NULL,64.969999999999998863,NULL,'','hnhy','','csv','2026-05-05 14:11:12');
   178|INSERT INTO "table" VALUES('000567','海德股份','深市','[]','多元金融',NULL,NULL,127.03999999999999737,NULL,'','hdgf','','csv','2026-05-05 14:11:07');
   179|INSERT INTO "table" VALUES('000568','泸州老窖','深市','[]','白酒Ⅱ',NULL,NULL,1473.019999999999996,NULL,'','lzlj','','csv','2026-05-05 14:11:09');
   180|INSERT INTO "table" VALUES('000569','长城股份','深市','[]','--',NULL,NULL,24.769999999999998685,NULL,'','ccgf','','csv','2026-05-05 14:11:09');
   181|INSERT INTO "table" VALUES('000570','苏常柴Ａ','深市','[]','汽车零部件',NULL,NULL,35.950000000000001953,NULL,'','sccＡ','','csv','2026-05-05 14:11:11');
   182|INSERT INTO "table" VALUES('000571','新大洲A','深市','[]','煤炭开采',NULL,NULL,45.579999999999998294,NULL,'','xdzA','','csv','2026-05-05 14:11:08');
   183|INSERT INTO "table" VALUES('000572','海马汽车','深市','[]','乘用车',NULL,NULL,91.639999999999997015,NULL,'','hmqc','','csv','2026-05-05 14:11:10');
   184|INSERT INTO "table" VALUES('000573','粤宏远Ａ','深市','[]','房地产开发',NULL,NULL,31.459999999999999076,NULL,'','yhyＡ','','csv','2026-05-05 14:11:07');
   185|INSERT INTO "table" VALUES('000576','甘化科工','深市','[]','地面兵装Ⅱ',NULL,NULL,38.090000000000001634,NULL,'','ghkg','','csv','2026-05-05 14:11:11');
   186|INSERT INTO "table" VALUES('000578','盐湖集团','深市','[]','--',NULL,NULL,62.090000000000005186,NULL,'','yhjt','','csv','2026-05-05 14:11:09');
   187|INSERT INTO "table" VALUES('000581','威孚高科','深市','[]','汽车零部件',NULL,NULL,154.56999999999998962,NULL,'','wfgk','','csv','2026-05-05 14:11:10');
   188|INSERT INTO "table" VALUES('000582','北部湾港','深市','[]','航运港口',NULL,NULL,244.5899999999999963,NULL,'','bbwg','','csv','2026-05-05 14:11:07');
   189|INSERT INTO "table" VALUES('000583','S*ST托普','深市','[]','--',NULL,NULL,0.99000000000000003552,NULL,'','S*STtp','','csv','2026-05-05 14:11:09');
   190|INSERT INTO "table" VALUES('000584','工智退','深市','[]','--',NULL,NULL,2.2000000000000001776,NULL,'','gzt','','csv','2026-05-05 14:11:09');
   191|INSERT INTO "table" VALUES('000585','东电退','深市','[]','--',NULL,NULL,2.1299999999999998934,NULL,'','ddt','','csv','2026-05-05 14:11:09');
   192|INSERT INTO "table" VALUES('000586','汇源通信','深市','[]','通信设备',NULL,NULL,33.709999999999999964,NULL,'','hytx','','csv','2026-05-05 14:11:12');
   193|INSERT INTO "table" VALUES('000587','*ST金洲','深市','[]','--',NULL,NULL,8.7300000000000004263,NULL,'','*STjz','','csv','2026-05-05 14:11:09');
   194|INSERT INTO "table" VALUES('000588','PT粤金曼','深市','[]','--',NULL,NULL,2.7099999999999999644,NULL,'','PTyjm','','csv','2026-05-05 14:11:09');
   195|INSERT INTO "table" VALUES('000589','贵州轮胎','深市','[]','汽车零部件',NULL,NULL,77.859999999999995878,NULL,'','gzlt','','csv','2026-05-05 14:11:10');
   196|INSERT INTO "table" VALUES('000590','古汉医药','深市','[]','中药Ⅱ',NULL,NULL,26.739999999999999324,NULL,'','ghyy','','csv','2026-05-05 14:11:09');
   197|INSERT INTO "table" VALUES('000591','太阳能','深市','[]','电力',NULL,NULL,196.21999999999999886,NULL,'','tyn','','csv','2026-05-05 14:11:09');
   198|INSERT INTO "table" VALUES('000592','平潭发展','深市','[]','林业Ⅱ',NULL,NULL,204.91000000000001435,NULL,'','ptfz','','csv','2026-05-05 14:11:07');
   199|INSERT INTO "table" VALUES('000593','德龙汇能','深市','[]','燃气Ⅱ',NULL,NULL,86.819999999999986073,NULL,'','dlhn','','csv','2026-05-05 14:11:06');
   200|INSERT INTO "table" VALUES('000594','国恒退','深市','[]','--',NULL,NULL,19.269999999999999573,NULL,'','ght','','csv','2026-05-05 14:11:09');
   201|INSERT INTO "table" VALUES('000595','*ST宝实','深市','[]','电力',NULL,NULL,72.299999999999995381,NULL,'','*STbs','','csv','2026-05-05 14:11:09');
   202|INSERT INTO "table" VALUES('000596','古井贡酒','深市','[]','白酒Ⅱ',NULL,NULL,441.73999999999997712,NULL,'','gjgj','','csv','2026-05-05 14:11:08');
   203|INSERT INTO "table" VALUES('000597','东北制药','深市','[]','化学制药',NULL,NULL,69.610000000000002984,NULL,'','dbzy','','csv','2026-05-05 14:11:09');
   204|INSERT INTO "table" VALUES('000598','兴蓉环境','深市','[]','环境治理',NULL,NULL,204.97000000000000774,NULL,'','xrhj','','csv','2026-05-05 14:11:08');
   205|INSERT INTO "table" VALUES('000599','青岛双星','深市','[]','汽车零部件',NULL,NULL,49.169999999999998152,NULL,'','qdsx','','csv','2026-05-05 14:11:07');
   206|INSERT INTO "table" VALUES('000600','建投能源','深市','[]','电力',NULL,NULL,104.09999999999999253,NULL,'','jtny','','csv','2026-05-05 14:11:08');
   207|INSERT INTO "table" VALUES('000601','韶能股份','深市','[]','电力',NULL,NULL,68.849999999999997868,NULL,'','sngf','','csv','2026-05-05 14:11:11');
   208|INSERT INTO "table" VALUES('000602','金马集团','深市','[]','--',NULL,NULL,28.010000000000001563,NULL,'','jmjt','','csv','2026-05-05 14:11:09');
   209|INSERT INTO "table" VALUES('000603','盛达资源','深市','[]','贵金属',NULL,NULL,244.15000000000000035,NULL,'','sdzy','','csv','2026-05-05 14:11:11');
   210|INSERT INTO "table" VALUES('000605','渤海股份','深市','[]','环境治理',NULL,NULL,25.499999999999998223,NULL,'','bhgf','','csv','2026-05-05 14:11:07');
   211|INSERT INTO "table" VALUES('000606','顺利退','深市','[]','--',NULL,NULL,2.1400000000000001243,NULL,'','slt','','csv','2026-05-05 14:11:09');
   212|INSERT INTO "table" VALUES('000607','华媒控股','深市','[]','广告营销',NULL,NULL,36.729999999999995985,NULL,'','hmkg','','csv','2026-05-05 14:11:08');
   213|INSERT INTO "table" VALUES('000608','*ST阳光','深市','[]','房地产开发',NULL,NULL,27.429999999999998827,NULL,'','*STyg','','csv','2026-05-05 14:11:10');
   214|INSERT INTO "table" VALUES('000609','*ST中迪','深市','[]','房地产开发',NULL,NULL,41.970000000000000639,NULL,'','*STzd','','csv','2026-05-05 14:11:07');
   215|INSERT INTO "table" VALUES('000610','*ST西旅','深市','[]','旅游及景区',NULL,NULL,18.390000000000000568,NULL,'','*STxl','','csv','2026-05-05 14:11:12');
   216|INSERT INTO "table" VALUES('000611','天首退','深市','[]','--',NULL,NULL,4.4400000000000003907,NULL,'','tst','','csv','2026-05-05 14:11:09');
   217|INSERT INTO "table" VALUES('000612','焦作万方','深市','[]','工业金属',NULL,NULL,158.68000000000000326,NULL,'','jzwf','','csv','2026-05-05 14:11:11');
   218|INSERT INTO "table" VALUES('000613','东海A退','深市','[]','--',NULL,NULL,1.55,NULL,'','dhAt','','csv','2026-05-05 14:11:09');
   219|INSERT INTO "table" VALUES('000615','*ST美谷','深市','[]','医疗美容',NULL,NULL,31.089999999999999857,NULL,'','*STmg','','csv','2026-05-05 14:11:11');
   220|INSERT INTO "table" VALUES('000616','*ST海投','深市','[]','--',NULL,NULL,12.159999999999999698,NULL,'','*STht','','csv','2026-05-05 14:11:09');
   221|INSERT INTO "table" VALUES('000617','中油资本','深市','[]','多元金融',NULL,NULL,1188.3599999999998608,NULL,'','zyzb','','csv','2026-05-05 14:11:09');
   222|INSERT INTO "table" VALUES('000618','吉林化工','深市','[]','--',NULL,NULL,10.480000000000000426,NULL,'','jlhg','','csv','2026-05-05 14:11:09');
   223|INSERT INTO "table" VALUES('000619','海螺新材','深市','[]','装修建材',NULL,NULL,22.32000000000000206,NULL,'','hlxc','','csv','2026-05-05 14:11:09');
   224|INSERT INTO "table" VALUES('000620','盈新发展','深市','[]','房地产开发',NULL,NULL,130.81000000000000405,NULL,'','yxfz','','csv','2026-05-05 14:11:09');
   225|INSERT INTO "table" VALUES('000621','*ST比特','深市','[]','--',NULL,NULL,1.4799999999999999822,NULL,'','*STbt','','csv','2026-05-05 14:11:09');
   226|INSERT INTO "table" VALUES('000622','恒立退','深市','[]','--',NULL,NULL,0.64000000000000003552,NULL,'','hlt','','csv','2026-05-05 14:11:09');
   227|INSERT INTO "table" VALUES('000623','吉林敖东','深市','[]','中药Ⅱ',NULL,NULL,224.96999999999998109,NULL,'','jlad','','csv','2026-05-05 14:11:07');
   228|INSERT INTO "table" VALUES('000625','长安汽车','深市','[]','乘用车',NULL,NULL,793.63999999999998991,NULL,'','caqc','','csv','2026-05-05 14:11:10');
   229|INSERT INTO "table" VALUES('000626','远大控股','深市','[]','物流',NULL,NULL,47.450000000000001065,NULL,'','ydkg','','csv','2026-05-05 14:11:07');
   230|INSERT INTO "table" VALUES('000627','*ST天茂','深市','[]','--',NULL,NULL,71.349999999999997868,NULL,'','*STtm','','csv','2026-05-05 14:11:09');
   231|INSERT INTO "table" VALUES('000628','高新发展','深市','[]','房屋建设Ⅱ',NULL,NULL,127.21999999999999975,NULL,'','gxfz','','csv','2026-05-05 14:11:10');
   232|INSERT INTO "table" VALUES('000629','钒钛股份','深市','[]','冶钢原料',NULL,NULL,338.17000000000003723,NULL,'','ftgf','','csv','2026-05-05 14:11:12');
   233|INSERT INTO "table" VALUES('000630','铜陵有色','深市','[]','工业金属',NULL,NULL,685.28999999999999914,NULL,'','tlys','','csv','2026-05-05 14:11:09');
   234|INSERT INTO "table" VALUES('000631','顺发恒能','深市','[]','电力',NULL,NULL,73.830000000000000071,NULL,'','sfhn','','csv','2026-05-05 14:11:09');
   235|INSERT INTO "table" VALUES('000632','ST三木','深市','[]','综合Ⅱ',NULL,NULL,18.149999999999998578,NULL,'','STsm','','csv','2026-05-05 14:11:10');
   236|INSERT INTO "table" VALUES('000633','合金投资','深市','[]','金属新材料',NULL,NULL,26.530000000000000248,NULL,'','hjtz','','csv','2026-05-05 14:11:09');
   237|INSERT INTO "table" VALUES('000635','英 力 特','深市','[]','化学原料',NULL,NULL,30.010000000000003339,NULL,'','y l t','','csv','2026-05-05 14:11:08');
   238|INSERT INTO "table" VALUES('000636','风华高科','深市','[]','元件',NULL,NULL,286.81999999999998607,NULL,'','fhgk','','csv','2026-05-05 14:11:07');
   239|INSERT INTO "table" VALUES('000637','茂化实华','深市','[]','炼化及贸易',NULL,NULL,17.459999999999999964,NULL,'','mhsh','','csv','2026-05-05 14:11:07');
   240|INSERT INTO "table" VALUES('000638','*ST万方','深市','[]','农产品加工',NULL,NULL,2.7700000000000000177,NULL,'','*STwf','','csv','2026-05-05 14:11:09');
   241|INSERT INTO "table" VALUES('000639','ST西王','深市','[]','食品加工',NULL,NULL,21.909999999999998365,NULL,'','STxw','','csv','2026-05-05 14:11:07');
   242|INSERT INTO "table" VALUES('000650','仁和药业','深市','[]','中药Ⅱ',NULL,NULL,76.019999999999994244,NULL,'','rhyy','','csv','2026-05-05 14:11:07');
   243|INSERT INTO "table" VALUES('000651','格力电器','深市','[]','白色家电',NULL,NULL,2222.6099999999999745,NULL,'','gldq','','csv','2026-05-05 14:11:07');
   244|INSERT INTO "table" VALUES('000652','泰达股份','深市','[]','综合Ⅱ',NULL,NULL,63.990000000000000213,NULL,'','tdgf','','csv','2026-05-05 14:11:07');
   245|INSERT INTO "table" VALUES('000653','ST九州','深市','[]','--',NULL,NULL,5.4500000000000001776,NULL,'','STjz','','csv','2026-05-05 14:11:09');
   246|INSERT INTO "table" VALUES('000655','金岭矿业','深市','[]','冶钢原料',NULL,NULL,49.350000000000004973,NULL,'','jlky','','csv','2026-05-05 14:11:10');
   247|INSERT INTO "table" VALUES('000656','*ST金科','深市','[]','房地产开发',NULL,NULL,105.88999999999999523,NULL,'','*STjk','','csv','2026-05-05 14:11:12');
   248|INSERT INTO "table" VALUES('000657','中钨高新','深市','[]','小金属',NULL,NULL,846.90999999999991842,NULL,'','zwgx','','csv','2026-05-05 14:11:12');
   249|INSERT INTO "table" VALUES('000658','ST海洋','深市','[]','--',NULL,NULL,4.2300000000000004263,NULL,'','SThy','','csv','2026-05-05 14:11:09');
   250|INSERT INTO "table" VALUES('000659','珠海中富','深市','[]','包装印刷',NULL,NULL,52.460000000000004405,NULL,'','zhzf','','csv','2026-05-05 14:11:08');
   251|INSERT INTO "table" VALUES('000660','*ST南华','深市','[]','--',NULL,NULL,0.93000000000000007105,NULL,'','*STnh','','csv','2026-05-05 14:11:09');
   252|INSERT INTO "table" VALUES('000661','长春高新','深市','[]','生物制品',NULL,NULL,339.94999999999997442,NULL,'','ccgx','','csv','2026-05-05 14:11:08');
   253|INSERT INTO "table" VALUES('000662','天夏退','深市','[]','--',NULL,NULL,2.7299999999999999822,NULL,'','txt','','csv','2026-05-05 14:11:09');
   254|INSERT INTO "table" VALUES('000663','永安林业','深市','[]','林业Ⅱ',NULL,NULL,21.100000000000003197,NULL,'','yaly','','csv','2026-05-05 14:11:07');
   255|INSERT INTO "table" VALUES('000665','湖北广电','深市','[]','电视广播Ⅱ',NULL,NULL,54.580000000000001847,NULL,'','hbgd','','csv','2026-05-05 14:11:07');
   256|INSERT INTO "table" VALUES('000666','经纬纺机','深市','[]','--',NULL,NULL,26.330000000000000071,NULL,'','jwfj','','csv','2026-05-05 14:11:09');
   257|INSERT INTO "table" VALUES('000667','ST美置','深市','[]','--',NULL,NULL,14.150000000000000355,NULL,'','STmz','','csv','2026-05-05 14:11:09');
   258|INSERT INTO "table" VALUES('000668','*ST荣控','深市','[]','房地产开发',NULL,NULL,23.220000000000000639,NULL,'','*STrk','','csv','2026-05-05 14:11:09');
   259|INSERT INTO "table" VALUES('000669','ST金鸿','深市','[]','燃气Ⅱ',NULL,NULL,28.579999999999996518,NULL,'','STjh','','csv','2026-05-05 14:11:07');
   260|INSERT INTO "table" VALUES('000670','盈方微','深市','[]','其他电子Ⅱ',NULL,NULL,61.890000000000000568,NULL,'','yfw','','csv','2026-05-05 14:11:12');
   261|INSERT INTO "table" VALUES('000671','ST阳光城','深市','[]','--',NULL,NULL,15.019999999999999573,NULL,'','STygc','','csv','2026-05-05 14:11:09');
   262|INSERT INTO "table" VALUES('000672','上峰水泥','深市','[]','水泥',NULL,NULL,127.27999999999999314,NULL,'','sfsn','','csv','2026-05-05 14:11:13');
   263|INSERT INTO "table" VALUES('000673','当代退','深市','[]','--',NULL,NULL,1.9699999999999999289,NULL,'','ddt','','csv','2026-05-05 14:11:09');
   264|INSERT INTO "table" VALUES('000675','ST银山','深市','[]','--',NULL,NULL,2.6299999999999998934,NULL,'','STys','','csv','2026-05-05 14:11:09');
   265|INSERT INTO "table" VALUES('000676','智度股份','深市','[]','广告营销',NULL,NULL,93.550000000000004263,NULL,'','zdgf','','csv','2026-05-05 14:11:10');
   266|INSERT INTO "table" VALUES('000677','恒天海龙','深市','[]','化学纤维',NULL,NULL,33.0,NULL,'','hthl','','csv','2026-05-05 14:11:12');
   267|INSERT INTO "table" VALUES('000678','襄阳轴承','深市','[]','汽车零部件',NULL,NULL,53.589999999999999857,NULL,'','xyzc','','csv','2026-05-05 14:11:11');
   268|INSERT INTO "table" VALUES('000679','大连友谊','深市','[]','一般零售',NULL,NULL,25.80000000000000071,NULL,'','dlyy','','csv','2026-05-05 14:11:08');
   269|INSERT INTO "table" VALUES('000680','山推股份','深市','[]','工程机械',NULL,NULL,159.33999999999999275,NULL,'','stgf','','csv','2026-05-05 14:11:07');
   270|INSERT INTO "table" VALUES('000681','视觉中国','深市','[]','数字媒体',NULL,NULL,148.47999999999998976,NULL,'','sjzg','','csv','2026-05-05 14:11:11');
   271|INSERT INTO "table" VALUES('000682','东方电子','深市','[]','电网设备',NULL,NULL,175.75000000000001065,NULL,'','dfdz','','csv','2026-05-05 14:11:11');
   272|INSERT INTO "table" VALUES('000683','博源化工','深市','[]','化学原料',NULL,NULL,301.12000000000000987,NULL,'','byhg','','csv','2026-05-05 14:11:08');
   273|INSERT INTO "table" VALUES('000685','中山公用','深市','[]','环境治理',NULL,NULL,147.33999999999999985,NULL,'','zsgy','','csv','2026-05-05 14:11:07');
   274|INSERT INTO "table" VALUES('000686','东北证券','深市','[]','证券Ⅱ',NULL,NULL,202.91999999999998927,NULL,'','dbzq','','csv','2026-05-05 14:11:08');
   275|INSERT INTO "table" VALUES('000687','华讯退','深市','[]','--',NULL,NULL,2.1800000000000001598,NULL,'','hxt','','csv','2026-05-05 14:11:09');
   276|INSERT INTO "table" VALUES('000688','国城矿业','深市','[]','工业金属',NULL,NULL,613.26999999999998181,NULL,'','gcky','','csv','2026-05-05 14:11:08');
   277|INSERT INTO "table" VALUES('000689','ST宏业','深市','[]','--',NULL,NULL,2.3900000000000001243,NULL,'','SThy','','csv','2026-05-05 14:11:09');
   278|INSERT INTO "table" VALUES('000690','宝新能源','深市','[]','电力',NULL,NULL,114.37999999999999278,NULL,'','bxny','','csv','2026-05-05 14:11:10');
   279|INSERT INTO "table" VALUES('000691','*ST亚太','深市','[]','化学原料',NULL,NULL,24.759999999999999786,NULL,'','*STyt','','csv','2026-05-05 14:11:12');
   280|INSERT INTO "table" VALUES('000692','惠天热电','深市','[]','电力',NULL,NULL,25.949999999999997513,NULL,'','htrd','','csv','2026-05-05 14:11:07');
   281|INSERT INTO "table" VALUES('000693','华泽退','深市','[]','--',NULL,NULL,0.95999999999999996447,NULL,'','hzt','','csv','2026-05-05 14:11:09');
   282|INSERT INTO "table" VALUES('000695','滨海能源','深市','[]','电池',NULL,NULL,34.619999999999997442,NULL,'','bhny','','csv','2026-05-05 14:11:08');
   283|INSERT INTO "table" VALUES('000697','ST炼石','深市','[]','航空装备Ⅱ',NULL,NULL,66.420000000000003481,NULL,'','STls','','csv','2026-05-05 14:11:08');
   284|INSERT INTO "table" VALUES('000698','ST沈化','深市','[]','炼化及贸易',NULL,NULL,30.489999999999999324,NULL,'','STsh','','csv','2026-05-05 14:11:09');
   285|INSERT INTO "table" VALUES('000699','S*ST佳纸','深市','[]','--',NULL,NULL,0.75999999999999996447,NULL,'','S*STjz','','csv','2026-05-05 14:11:09');
   286|INSERT INTO "table" VALUES('000700','模塑科技','深市','[]','汽车零部件',NULL,NULL,112.27000000000000312,NULL,'','mskj','','csv','2026-05-05 14:11:12');
   287|INSERT INTO "table" VALUES('000701','厦门信达','深市','[]','贸易Ⅱ',NULL,NULL,39.799999999999995381,NULL,'','xmxd','','csv','2026-05-05 14:11:08');
   288|INSERT INTO "table" VALUES('000702','正虹科技','深市','[]','饲料',NULL,NULL,18.960000000000000852,NULL,'','zhkj','','csv','2026-05-05 14:11:07');
   289|INSERT INTO "table" VALUES('000703','恒逸石化','深市','[]','炼化及贸易',NULL,NULL,672.55999999999991345,NULL,'','hysh','','csv','2026-05-05 14:11:07');
   290|INSERT INTO "table" VALUES('000705','浙江震元','深市','[]','医药商业',NULL,NULL,23.399999999999998578,NULL,'','zjzy','','csv','2026-05-05 14:11:07');
   291|INSERT INTO "table" VALUES('000707','双环科技','深市','[]','化学原料',NULL,NULL,32.990000000000003765,NULL,'','shkj','','csv','2026-05-05 14:11:07');
   292|INSERT INTO "table" VALUES('000708','中信特钢','深市','[]','特钢Ⅱ',NULL,NULL,775.74000000000005172,NULL,'','zxtg','','csv','2026-05-05 14:11:07');
   293|INSERT INTO "table" VALUES('000709','河钢股份','深市','[]','普钢',NULL,NULL,240.81999999999998962,NULL,'','hggf','','csv','2026-05-05 14:11:09');
   294|INSERT INTO "table" VALUES('000710','贝瑞基因','深市','[]','医疗服务',NULL,NULL,32.890000000000001456,NULL,'','brjy','','csv','2026-05-05 14:11:10');
   295|INSERT INTO "table" VALUES('000711','ST京蓝','深市','[]','环境治理',NULL,NULL,114.77999999999999314,NULL,'','STjl','','csv','2026-05-05 14:11:07');
   296|INSERT INTO "table" VALUES('000712','锦龙股份','深市','[]','证券Ⅱ',NULL,NULL,92.980000000000000426,NULL,'','jlgf','','csv','2026-05-05 14:11:08');
   297|INSERT INTO "table" VALUES('000713','国投丰乐','深市','[]','种植业',NULL,NULL,39.909999999999996589,NULL,'','gtfl','','csv','2026-05-05 14:11:08');
   298|INSERT INTO "table" VALUES('000715','中兴商业','深市','[]','一般零售',NULL,NULL,29.27999999999999936,NULL,'','zxsy','','csv','2026-05-05 14:11:12');
   299|INSERT INTO "table" VALUES('000716','黑芝麻','深市','[]','休闲食品',NULL,NULL,38.039999999999999147,NULL,'','hzm','','csv','2026-05-05 14:11:07');
   300|INSERT INTO "table" VALUES('000717','中南股份','深市','[]','普钢',NULL,NULL,60.350000000000001421,NULL,'','zngf','','csv','2026-05-05 14:11:07');
   301|INSERT INTO "table" VALUES('000718','苏宁环球','深市','[]','房地产开发',NULL,NULL,49.740000000000001989,NULL,'','snhq','','csv','2026-05-05 14:11:09');
   302|INSERT INTO "table" VALUES('000719','中原传媒','深市','[]','出版',NULL,NULL,89.730000000000007531,NULL,'','zycm','','csv','2026-05-05 14:11:07');
   303|INSERT INTO "table" VALUES('000720','新能泰山','深市','[]','电网设备',NULL,NULL,56.920000000000001705,NULL,'','xnts','','csv','2026-05-05 14:11:11');
   304|INSERT INTO "table" VALUES('000721','西安饮食','深市','[]','酒店餐饮',NULL,NULL,38.990000000000000213,NULL,'','xays','','csv','2026-05-05 14:11:10');
   305|INSERT INTO "table" VALUES('000722','湖南发展','深市','[]','电力',NULL,NULL,66.470000000000002415,NULL,'','hnfz','','csv','2026-05-05 14:11:07');
   306|INSERT INTO "table" VALUES('000723','美锦能源','深市','[]','焦炭Ⅱ',NULL,NULL,196.90000000000001278,NULL,'','mjny','','csv','2026-05-05 14:11:07');
   307|INSERT INTO "table" VALUES('000725','京东方Ａ','深市','[]','光学光电子',NULL,NULL,1490.0100000000000122,NULL,'','jdfＡ','','csv','2026-05-05 14:11:10');
   308|INSERT INTO "table" VALUES('000726','鲁  泰Ａ','深市','[]','纺织制造',NULL,NULL,38.780000000000001136,NULL,'','l  tＡ','','csv','2026-05-05 14:11:09');
   309|INSERT INTO "table" VALUES('000727','冠捷科技','深市','[]','光学光电子',NULL,NULL,120.02999999999999225,NULL,'','gjkj','','csv','2026-05-05 14:11:10');
   310|INSERT INTO "table" VALUES('000728','国元证券','深市','[]','证券Ⅱ',NULL,NULL,321.60999999999999587,NULL,'','gyzq','','csv','2026-05-05 14:11:09');
   311|INSERT INTO "table" VALUES('000729','燕京啤酒','深市','[]','非白酒',NULL,NULL,333.27999999999997626,NULL,'','yjpj','','csv','2026-05-05 14:11:07');
   312|INSERT INTO "table" VALUES('000730','*ST环保','深市','[]','--',NULL,NULL,5.0300000000000002486,NULL,'','*SThb','','csv','2026-05-05 14:11:09');
   313|INSERT INTO "table" VALUES('000731','四川美丰','深市','[]','农化制品',NULL,NULL,39.790000000000000923,NULL,'','scmf','','csv','2026-05-05 14:11:07');
   314|INSERT INTO "table" VALUES('000732','ST泰禾','深市','[]','--',NULL,NULL,10.689999999999999502,NULL,'','STth','','csv','2026-05-05 14:11:09');
   315|INSERT INTO "table" VALUES('000733','振华科技','深市','[]','军工电子Ⅱ',NULL,NULL,234.33000000000001605,NULL,'','zhkj','','csv','2026-05-05 14:11:09');
   316|INSERT INTO "table" VALUES('000735','罗 牛 山','深市','[]','养殖业',NULL,NULL,75.379999999999993676,NULL,'','l n s','','csv','2026-05-05 14:11:12');
   317|INSERT INTO "table" VALUES('000736','*ST中地','深市','[]','房地产开发',NULL,NULL,41.390000000000002344,NULL,'','*STzd','','csv','2026-05-05 14:11:09');
   318|INSERT INTO "table" VALUES('000737','北方铜业','深市','[]','工业金属',NULL,NULL,274.62999999999997413,NULL,'','bfty','','csv','2026-05-05 14:11:10');
   319|INSERT INTO "table" VALUES('000738','航发控制','深市','[]','航空装备Ⅱ',NULL,NULL,273.30000000000000959,NULL,'','hfkz','','csv','2026-05-05 14:11:12');
   320|INSERT INTO "table" VALUES('000739','普洛药业','深市','[]','化学制药',NULL,NULL,209.24999999999998046,NULL,'','plyy','','csv','2026-05-05 14:11:08');
   321|INSERT INTO "table" VALUES('000748','长城信息','深市','[]','--',NULL,NULL,162.90000000000000035,NULL,'','ccxx','','csv','2026-05-05 14:11:09');
   322|INSERT INTO "table" VALUES('000750','国海证券','深市','[]','证券Ⅱ',NULL,NULL,226.04999999999999538,NULL,'','ghzq','','csv','2026-05-05 14:11:08');
   323|INSERT INTO "table" VALUES('000751','锌业股份','深市','[]','工业金属',NULL,NULL,85.719999999999991757,NULL,'','xygf','','csv','2026-05-05 14:11:12');
   324|INSERT INTO "table" VALUES('000752','*ST西发','深市','[]','非白酒',NULL,NULL,26.450000000000000177,NULL,'','*STxf','','csv','2026-05-05 14:11:07');
   325|INSERT INTO "table" VALUES('000753','漳州发展','深市','[]','综合Ⅱ',NULL,NULL,64.249999999999998223,NULL,'','zzfz','','csv','2026-05-05 14:11:06');
   326|INSERT INTO "table" VALUES('000755','山西高速','深市','[]','铁路公路',NULL,NULL,73.510000000000008668,NULL,'','sxgs','','csv','2026-05-05 14:11:08');
   327|INSERT INTO "table" VALUES('000756','新华制药','深市','[]','化学制药',NULL,NULL,70.590000000000001634,NULL,'','xhzy','','csv','2026-05-05 14:11:08');
   328|INSERT INTO "table" VALUES('000757','浩物股份','深市','[]','汽车服务',NULL,NULL,26.209999999999999964,NULL,'','hwgf','','csv','2026-05-05 14:11:09');
   329|INSERT INTO "table" VALUES('000758','中色股份','深市','[]','工业金属',NULL,NULL,138.72999999999999687,NULL,'','zsgf','','csv','2026-05-05 14:11:10');
   330|INSERT INTO "table" VALUES('000759','中百集团','深市','[]','一般零售',NULL,NULL,36.189999999999997726,NULL,'','zbjt','','csv','2026-05-05 14:11:10');
   331|INSERT INTO "table" VALUES('000760','斯太退','深市','[]','--',NULL,NULL,1.7,NULL,'','stt','','csv','2026-05-05 14:11:09');
   332|INSERT INTO "table" VALUES('000761','本钢板材','深市','[]','普钢',NULL,NULL,110.88000000000000078,NULL,'','bgbc','','csv','2026-05-05 14:11:08');
   333|INSERT INTO "table" VALUES('000762','西藏矿业','深市','[]','能源金属',NULL,NULL,201.71000000000001151,NULL,'','xzky','','csv','2026-05-05 14:11:10');
   334|INSERT INTO "table" VALUES('000763','锦州石化','深市','[]','--',NULL,NULL,6.330000000000000071,NULL,'','jzsh','','csv','2026-05-05 14:11:09');
   335|INSERT INTO "table" VALUES('000765','*ST华信','深市','[]','--',NULL,NULL,14.289999999999998259,NULL,'','*SThx','','csv','2026-05-05 14:11:09');
   336|INSERT INTO "table" VALUES('000766','通化金马','深市','[]','化学制药',NULL,NULL,232.81000000000000582,NULL,'','thjm','','csv','2026-05-05 14:11:08');
   337|INSERT INTO "table" VALUES('000767','晋控电力','深市','[]','电力',NULL,NULL,110.95999999999999197,NULL,'','jkdl','','csv','2026-05-05 14:11:07');
   338|INSERT INTO "table" VALUES('000768','中航西飞','深市','[]','航空装备Ⅱ',NULL,NULL,655.22999999999997911,NULL,'','zhxf','','csv','2026-05-05 14:11:10');
   339|INSERT INTO "table" VALUES('000769','*ST大菲','深市','[]','--',NULL,NULL,0.72999999999999998223,NULL,'','*STdf','','csv','2026-05-05 14:11:09');
   340|INSERT INTO "table" VALUES('000776','广发证券','深市','[]','证券Ⅱ',NULL,NULL,1252.8399999999999536,NULL,'','gfzq','','csv','2026-05-05 14:11:06');
   341|INSERT INTO "table" VALUES('000777','中核科技','深市','[]','通用设备',NULL,NULL,76.109999999999997655,NULL,'','zhkj','','csv','2026-05-05 14:11:13');
   342|INSERT INTO "table" VALUES('000778','新兴铸管','深市','[]','普钢',NULL,NULL,179.87999999999999545,NULL,'','xxzg','','csv','2026-05-05 14:11:07');
   343|INSERT INTO "table" VALUES('000779','甘咨询','深市','[]','工程咨询服务Ⅱ',NULL,NULL,40.950000000000006394,NULL,'','gzx','','csv','2026-05-05 14:11:09');
   344|INSERT INTO "table" VALUES('000780','ST平能','深市','[]','--',NULL,NULL,111.07000000000000206,NULL,'','STpn','','csv','2026-05-05 14:11:09');
   345|INSERT INTO "table" VALUES('000782','恒申新材','深市','[]','化学纤维',NULL,NULL,38.770000000000003126,NULL,'','hsxc','','csv','2026-05-05 14:11:07');
   346|INSERT INTO "table" VALUES('000783','长江证券','深市','[]','证券Ⅱ',NULL,NULL,441.84999999999998721,NULL,'','cjzq','','csv','2026-05-05 14:11:07');
   347|INSERT INTO "table" VALUES('000785','居然智家','深市','[]','一般零售',NULL,NULL,150.34000000000000696,NULL,'','jrzj','','csv','2026-05-05 14:11:07');
   348|INSERT INTO "table" VALUES('000786','北新建材','深市','[]','装修建材',NULL,NULL,436.39999999999998792,NULL,'','bxjc','','csv','2026-05-05 14:11:07');
   349|INSERT INTO "table" VALUES('000787','*ST创智','深市','[]','--',NULL,NULL,12.630000000000001225,NULL,'','*STcz','','csv','2026-05-05 14:11:09');
   350|INSERT INTO "table" VALUES('000788','北大医药','深市','[]','化学制药',NULL,NULL,36.710000000000002629,NULL,'','bdyy','','csv','2026-05-05 14:11:07');
   351|INSERT INTO "table" VALUES('000789','万年青','深市','[]','水泥',NULL,NULL,39.630000000000000781,NULL,'','wnq','','csv','2026-05-05 14:11:10');
   352|INSERT INTO "table" VALUES('000790','华神科技','深市','[]','中药Ⅱ',NULL,NULL,28.449999999999997513,NULL,'','hskj','','csv','2026-05-05 14:11:08');
   353|INSERT INTO "table" VALUES('000791','甘肃能源','深市','[]','电力',NULL,NULL,156.2100000000000044,NULL,'','gsny','','csv','2026-05-05 14:11:09');
   354|INSERT INTO "table" VALUES('000792','盐湖股份','深市','[]','农化制品',NULL,NULL,2114.4899999999999806,NULL,'','yhgf','','csv','2026-05-05 14:11:10');
   355|INSERT INTO "table" VALUES('000793','*ST华闻','深市','[]','出版',NULL,NULL,53.72999999999999332,NULL,'','*SThw','','csv','2026-05-05 14:11:12');
   356|INSERT INTO "table" VALUES('000795','英洛华','深市','[]','金属新材料',NULL,NULL,104.53000000000001179,NULL,'','ylh','','csv','2026-05-05 14:11:11');
   357|INSERT INTO "table" VALUES('000796','凯撒旅业','深市','[]','旅游及景区',NULL,NULL,69.199999999999999289,NULL,'','ksly','','csv','2026-05-05 14:11:11');
   358|INSERT INTO "table" VALUES('000797','中国武夷','深市','[]','房地产开发',NULL,NULL,45.229999999999996873,NULL,'','zgwy','','csv','2026-05-05 14:11:10');
   359|INSERT INTO "table" VALUES('000798','中水渔业','深市','[]','渔业',NULL,NULL,34.210000000000002629,NULL,'','zsyy','','csv','2026-05-05 14:11:08');
   360|INSERT INTO "table" VALUES('000799','酒鬼酒','深市','[]','白酒Ⅱ',NULL,NULL,139.90000000000000213,NULL,'','jgj','','csv','2026-05-05 14:11:11');
   361|INSERT INTO "table" VALUES('000800','一汽解放','深市','[]','商用车',NULL,NULL,334.12000000000001698,NULL,'','yqjf','','csv','2026-05-05 14:11:09');
   362|INSERT INTO "table" VALUES('000801','四川九洲','深市','[]','黑色家电',NULL,NULL,130.04000000000000003,NULL,'','scjz','','csv','2026-05-05 14:11:13');
   363|INSERT INTO "table" VALUES('000802','北京文化','深市','[]','影视院线',NULL,NULL,30.840000000000000746,NULL,'','bjwh','','csv','2026-05-05 14:11:09');
   364|INSERT INTO "table" VALUES('000803','山高环能','深市','[]','电力',NULL,NULL,39.590000000000005186,NULL,'','sghn','','csv','2026-05-05 14:11:08');
   365|INSERT INTO "table" VALUES('000805','*ST炎黄','深市','[]','--',NULL,NULL,0.39000000000000003552,NULL,'','*STyh','','csv','2026-05-05 14:11:09');
   366|INSERT INTO "table" VALUES('000806','银河退','深市','[]','--',NULL,NULL,3.7900000000000000355,NULL,'','yht','','csv','2026-05-05 14:11:09');
   367|INSERT INTO "table" VALUES('000807','云铝股份','深市','[]','工业金属',NULL,NULL,1108.0,NULL,'','ylgf','','csv','2026-05-05 14:11:11');
   368|INSERT INTO "table" VALUES('000809','和展能源','深市','[]','风电设备',NULL,NULL,31.260000000000003339,NULL,'','hzny','','csv','2026-05-05 14:11:07');
   369|INSERT INTO "table" VALUES('000810','创维数字','深市','[]','黑色家电',NULL,NULL,141.05000000000000426,NULL,'','cwsz','','csv','2026-05-05 14:11:10');
   370|INSERT INTO "table" VALUES('000811','冰轮环境','深市','[]','通用设备',NULL,NULL,245.08999999999998564,NULL,'','blhj','','csv','2026-05-05 14:11:06');
   371|INSERT INTO "table" VALUES('000812','陕西金叶','深市','[]','包装印刷',NULL,NULL,30.929999999999999715,NULL,'','sxjy','','csv','2026-05-05 14:11:10');
   372|INSERT INTO "table" VALUES('000813','德展健康','深市','[]','化学制药',NULL,NULL,76.950000000000002842,NULL,'','dzjk','','csv','2026-05-05 14:11:07');
   373|INSERT INTO "table" VALUES('000815','美利云','深市','[]','IT服务Ⅱ',NULL,NULL,133.9099999999999957,NULL,'','mly','','csv','2026-05-05 14:11:07');
   374|INSERT INTO "table" VALUES('000816','智慧农业','深市','[]','汽车零部件',NULL,NULL,46.210000000000004405,NULL,'','zhny','','csv','2026-05-05 14:11:09');
   375|INSERT INTO "table" VALUES('000817','辽河油田','深市','[]','--',NULL,NULL,17.5,NULL,'','lhyt','','csv','2026-05-05 14:11:09');
   376|INSERT INTO "table" VALUES('000818','航锦科技','深市','[]','化学原料',NULL,NULL,102.15000000000000746,NULL,'','hjkj','','csv','2026-05-05 14:11:09');
   377|INSERT INTO "table" VALUES('000819','岳阳兴长','深市','[]','炼化及贸易',NULL,NULL,59.689999999999994173,NULL,'','yyxz','','csv','2026-05-05 14:11:10');
   378|INSERT INTO "table" VALUES('000820','*ST节能','深市','[]','环保设备Ⅱ',NULL,NULL,11.339999999999998969,NULL,'','*STjn','','csv','2026-05-05 14:11:07');
   379|INSERT INTO "table" VALUES('000821','ST京机','深市','[]','光伏设备',NULL,NULL,62.580000000000000071,NULL,'','STjj','','csv','2026-05-05 14:11:12');
   380|INSERT INTO "table" VALUES('000822','山东海化','深市','[]','化学原料',NULL,NULL,53.079999999999998294,NULL,'','sdhh','','csv','2026-05-05 14:11:09');
   381|INSERT INTO "table" VALUES('000823','超声电子','深市','[]','元件',NULL,NULL,79.739999999999993107,NULL,'','csdz','','csv','2026-05-05 14:11:11');
   382|INSERT INTO "table" VALUES('000825','太钢不锈','深市','[]','特钢Ⅱ',NULL,NULL,243.22999999999996845,NULL,'','tgbx','','csv','2026-05-05 14:11:13');
   383|INSERT INTO "table" VALUES('000826','*ST启环','深市','[]','环境治理',NULL,NULL,26.370000000000000106,NULL,'','*STqh','','csv','2026-05-05 14:11:07');
   384|INSERT INTO "table" VALUES('000827','*ST长兴','深市','[]','--',NULL,NULL,0.34000000000000003552,NULL,'','*STcx','','csv','2026-05-05 14:11:09');
   385|INSERT INTO "table" VALUES('000828','东莞控股','深市','[]','铁路公路',NULL,NULL,107.68999999999999683,NULL,'','dgkg','','csv','2026-05-05 14:11:07');
   386|INSERT INTO "table" VALUES('000829','天音控股','深市','[]','专业连锁Ⅱ',NULL,NULL,120.34000000000000252,NULL,'','tykg','','csv','2026-05-05 14:11:12');
   387|INSERT INTO "table" VALUES('000830','鲁西化工','深市','[]','化学原料',NULL,NULL,321.81000000000001826,NULL,'','lxhg','','csv','2026-05-05 14:11:07');
   388|INSERT INTO "table" VALUES('000831','中国稀土','深市','[]','小金属',NULL,NULL,579.21000000000004703,NULL,'','zgxt','','csv','2026-05-05 14:11:10');
   389|INSERT INTO "table" VALUES('000832','*ST龙涤','深市','[]','--',NULL,NULL,2.6600000000000001421,NULL,'','*STld','','csv','2026-05-05 14:11:09');
   390|INSERT INTO "table" VALUES('000833','粤桂股份','深市','[]','综合Ⅱ',NULL,NULL,134.52000000000001733,NULL,'','yggf','','csv','2026-05-05 14:11:08');
   391|INSERT INTO "table" VALUES('000835','长动退','深市','[]','--',NULL,NULL,1.1399999999999999023,NULL,'','zdt','','csv','2026-05-05 14:11:09');
   392|INSERT INTO "table" VALUES('000836','ST富通','深市','[]','--',NULL,NULL,4.4699999999999997513,NULL,'','STft','','csv','2026-05-05 14:11:09');
   393|INSERT INTO "table" VALUES('000837','秦川机床','深市','[]','通用设备',NULL,NULL,112.32999999999999651,NULL,'','qcjc','','csv','2026-05-05 14:11:10');
   394|INSERT INTO "table" VALUES('000838','*ST发展','深市','[]','房地产开发',NULL,NULL,20.550000000000001598,NULL,'','*STfz','','csv','2026-05-05 14:11:07');
   395|INSERT INTO "table" VALUES('000839','国安股份','深市','[]','通信服务',NULL,NULL,116.80999999999999161,NULL,'','gagf','','csv','2026-05-05 14:11:13');
   396|INSERT INTO "table" VALUES('000848','承德露露','深市','[]','饮料乳品',NULL,NULL,89.589999999999996305,NULL,'','cdll','','csv','2026-05-05 14:11:06');
   397|INSERT INTO "table" VALUES('000850','华茂股份','深市','[]','纺织制造',NULL,NULL,43.109999999999999431,NULL,'','hmgf','','csv','2026-05-05 14:11:12');
   398|INSERT INTO "table" VALUES('000851','*ST高鸿','深市','[]','--',NULL,NULL,4.2999999999999998223,NULL,'','*STgh','','csv','2026-05-05 14:11:09');
   399|INSERT INTO "table" VALUES('000852','石化机械','深市','[]','专用设备',NULL,NULL,68.390000000000004121,NULL,'','shjx','','csv','2026-05-05 14:11:10');
   400|INSERT INTO "table" VALUES('000856','冀东装备','深市','[]','专用设备',NULL,NULL,23.129999999999997228,NULL,'','jdzb','','csv','2026-05-05 14:11:13');
   401|INSERT INTO "table" VALUES('000858','五 粮 液','深市','[]','白酒Ⅱ',NULL,NULL,3768.8800000000002299,NULL,'','w l y','','csv','2026-05-05 14:11:09');
   402|INSERT INTO "table" VALUES('000859','国风新材','深市','[]','塑料',NULL,NULL,81.0800000000000054,NULL,'','gfxc','','csv','2026-05-05 14:11:10');
   403|INSERT INTO "table" VALUES('000860','顺鑫农业','深市','[]','白酒Ⅱ',NULL,NULL,94.430000000000013926,NULL,'','sxny','','csv','2026-05-05 14:11:08');
   404|INSERT INTO "table" VALUES('000861','海印股份','深市','[]','--',NULL,NULL,14.869999999999999218,NULL,'','hygf','','csv','2026-05-05 14:11:09');
   405|INSERT INTO "table" VALUES('000862','银星能源','深市','[]','电力',NULL,NULL,41.07000000000000206,NULL,'','yxny','','csv','2026-05-05 14:11:10');
   406|INSERT INTO "table" VALUES('000863','三湘印象','深市','[]','房地产开发',NULL,NULL,54.790000000000000923,NULL,'','sxyx','','csv','2026-05-05 14:11:07');
   407|INSERT INTO "table" VALUES('000866','扬子石化','深市','[]','--',NULL,NULL,48.439999999999994173,NULL,'','yzsh','','csv','2026-05-05 14:11:09');
   408|INSERT INTO "table" VALUES('000868','安凯客车','深市','[]','商用车',NULL,NULL,33.0,NULL,'','akkc','','csv','2026-05-05 14:11:08');
   409|INSERT INTO "table" VALUES('000869','张  裕Ａ','深市','[]','非白酒',NULL,NULL,87.609999999999992326,NULL,'','z  yＡ','','csv','2026-05-05 14:11:07');
   410|INSERT INTO "table" VALUES('000875','电投绿能','深市','[]','电力',NULL,NULL,215.91999999999997861,NULL,'','dtln','','csv','2026-05-05 14:11:09');
   411|INSERT INTO "table" VALUES('000876','新 希 望','深市','[]','养殖业',NULL,NULL,390.60000000000002273,NULL,'','x x w','','csv','2026-05-05 14:11:07');
   412|INSERT INTO "table" VALUES('000877','天山股份','深市','[]','水泥',NULL,NULL,330.64000000000000056,NULL,'','tsgf','','csv','2026-05-05 14:11:10');
   413|INSERT INTO "table" VALUES('000878','云南铜业','深市','[]','工业金属',NULL,NULL,382.88999999999999701,NULL,'','ynty','','csv','2026-05-05 14:11:11');
   414|INSERT INTO "table" VALUES('000880','潍柴重机','深市','[]','汽车零部件',NULL,NULL,70.019999999999997797,NULL,'','wczj','','csv','2026-05-05 14:11:12');
   415|INSERT INTO "table" VALUES('000881','中广核技','深市','[]','化学制品',NULL,NULL,70.489999999999994884,NULL,'','zghj','','csv','2026-05-05 14:11:09');
   416|INSERT INTO "table" VALUES('000882','华联股份','深市','[]','一般零售',NULL,NULL,45.400000000000000355,NULL,'','hlgf','','csv','2026-05-05 14:11:08');
   417|INSERT INTO "table" VALUES('000883','湖北能源','深市','[]','电力',NULL,NULL,314.91000000000002323,NULL,'','hbny','','csv','2026-05-05 14:11:07');
   418|INSERT INTO "table" VALUES('000885','城发环境','深市','[]','环境治理',NULL,NULL,90.530000000000008242,NULL,'','cfhj','','csv','2026-05-05 14:11:08');
   419|INSERT INTO "table" VALUES('000886','海南高速','深市','[]','铁路公路',NULL,NULL,54.070000000000000284,NULL,'','hngs','','csv','2026-05-05 14:11:10');
   420|INSERT INTO "table" VALUES('000887','中鼎股份','深市','[]','汽车零部件',NULL,NULL,230.2799999999999958,NULL,'','zdgf','','csv','2026-05-05 14:11:13');
   421|INSERT INTO "table" VALUES('000888','峨眉山Ａ','深市','[]','旅游及景区',NULL,NULL,62.069999999999998507,NULL,'','emsＡ','','csv','2026-05-05 14:11:11');
   422|INSERT INTO "table" VALUES('000889','中嘉博创','深市','[]','通信服务',NULL,NULL,38.530000000000001136,NULL,'','zjbc','','csv','2026-05-05 14:11:06');
   423|INSERT INTO "table" VALUES('000890','法尔胜','深市','[]','环保设备Ⅱ',NULL,NULL,64.939999999999997726,NULL,'','fes','','csv','2026-05-05 14:11:12');
   424|INSERT INTO "table" VALUES('000892','欢瑞世纪','深市','[]','影视院线',NULL,NULL,35.25999999999999801,NULL,'','hrsj','','csv','2026-05-05 14:11:12');
   425|INSERT INTO "table" VALUES('000893','亚钾国际','深市','[]','农化制品',NULL,NULL,439.51000000000002287,NULL,'','yjgj','','csv','2026-05-05 14:11:08');
   426|INSERT INTO "table" VALUES('000895','双汇发展','深市','[]','食品加工',NULL,NULL,959.59000000000003183,NULL,'','shfz','','csv','2026-05-05 14:11:07');
   427|INSERT INTO "table" VALUES('000897','津滨发展','深市','[]','房地产开发',NULL,NULL,35.420000000000002593,NULL,'','jbfz','','csv','2026-05-05 14:11:07');
   428|INSERT INTO "table" VALUES('000898','鞍钢股份','深市','[]','普钢',NULL,NULL,182.22999999999998976,NULL,'','aggf','','csv','2026-05-05 14:11:09');
   429|INSERT INTO "table" VALUES('000899','赣能股份','深市','[]','电力',NULL,NULL,122.44999999999999218,NULL,'','gngf','','csv','2026-05-05 14:11:12');
   430|INSERT INTO "table" VALUES('000900','现代投资','深市','[]','铁路公路',NULL,NULL,63.589999999999999857,NULL,'','xdtz','','csv','2026-05-05 14:11:07');
   431|INSERT INTO "table" VALUES('000901','航天科技','深市','[]','汽车零部件',NULL,NULL,191.40999999999998237,NULL,'','htkj','','csv','2026-05-05 14:11:12');
   432|INSERT INTO "table" VALUES('000902','新洋丰','深市','[]','农化制品',NULL,NULL,174.72999999999998976,NULL,'','xyf','','csv','2026-05-05 14:11:08');
   433|INSERT INTO "table" VALUES('000903','ST云动','深市','[]','汽车零部件',NULL,NULL,42.05000000000000071,NULL,'','STyd','','csv','2026-05-05 14:11:12');
   434|INSERT INTO "table" VALUES('000905','厦门港务','深市','[]','航运港口',NULL,NULL,80.120000000000004547,NULL,'','xmgw','','csv','2026-05-05 14:11:08');
   435|INSERT INTO "table" VALUES('000906','浙商中拓','深市','[]','物流',NULL,NULL,44.599999999999999644,NULL,'','zszt','','csv','2026-05-05 14:11:12');
   436|INSERT INTO "table" VALUES('000908','ST景峰','深市','[]','化学制药',NULL,NULL,62.900000000000000355,NULL,'','STjf','','csv','2026-05-05 14:11:07');
   437|INSERT INTO "table" VALUES('000909','*ST数源','深市','[]','房地产开发',NULL,NULL,20.400000000000000355,NULL,'','*STsy','','csv','2026-05-05 14:11:12');
   438|INSERT INTO "table" VALUES('000910','大亚圣象','深市','[]','家居用品',NULL,NULL,37.479999999999997761,NULL,'','dysx','','csv','2026-05-05 14:11:09');
   439|INSERT INTO "table" VALUES('000911','*ST广糖','深市','[]','农产品加工',NULL,NULL,22.94000000000000039,NULL,'','*STgt','','csv','2026-05-05 14:11:07');
   440|INSERT INTO "table" VALUES('000912','泸天化','深市','[]','农化制品',NULL,NULL,76.989999999999998436,NULL,'','lth','','csv','2026-05-05 14:11:07');
   441|INSERT INTO "table" VALUES('000913','钱江摩托','深市','[]','摩托车及其他',NULL,NULL,70.209999999999990194,NULL,'','qjmt','','csv','2026-05-05 14:11:08');
   442|INSERT INTO "table" VALUES('000915','华特达因','深市','[]','化学制药',NULL,NULL,67.439999999999997726,NULL,'','htdy','','csv','2026-05-05 14:11:08');
   443|INSERT INTO "table" VALUES('000916','华北高速','深市','[]','--',NULL,NULL,96.140000000000007673,NULL,'','hbgs','','csv','2026-05-05 14:11:09');
   444|INSERT INTO "table" VALUES('000917','电广传媒','深市','[]','电视广播Ⅱ',NULL,NULL,124.0299999999999958,NULL,'','dgcm','','csv','2026-05-05 14:11:13');
   445|INSERT INTO "table" VALUES('000918','*ST嘉凯','深市','[]','--',NULL,NULL,8.8399999999999998578,NULL,'','*STjk','','csv','2026-05-05 14:11:09');
   446|INSERT INTO "table" VALUES('000919','金陵药业','深市','[]','化学制药',NULL,NULL,45.890000000000004121,NULL,'','jlyy','','csv','2026-05-05 14:11:08');
   447|INSERT INTO "table" VALUES('000920','沃顿科技','深市','[]','塑料',NULL,NULL,54.919999999999999928,NULL,'','wdkj','','csv','2026-05-05 14:11:09');
   448|INSERT INTO "table" VALUES('000921','海信家电','深市','[]','白色家电',NULL,NULL,220.35000000000000142,NULL,'','hxjd','','csv','2026-05-05 14:11:07');
   449|INSERT INTO "table" VALUES('000922','佳电股份','深市','[]','电机Ⅱ',NULL,NULL,87.409999999999996589,NULL,'','jdgf','','csv','2026-05-05 14:11:07');
   450|INSERT INTO "table" VALUES('000923','河钢资源','深市','[]','冶钢原料',NULL,NULL,105.98999999999998422,NULL,'','hgzy','','csv','2026-05-05 14:11:10');
   451|INSERT INTO "table" VALUES('000925','众合科技','深市','[]','轨交设备Ⅱ',NULL,NULL,62.409999999999996589,NULL,'','zhkj','','csv','2026-05-05 14:11:12');
   452|INSERT INTO "table" VALUES('000926','福星股份','深市','[]','房地产开发',NULL,NULL,33.349999999999999644,NULL,'','fxgf','','csv','2026-05-05 14:11:07');
   453|INSERT INTO "table" VALUES('000927','中国铁物','深市','[]','轨交设备Ⅱ',NULL,NULL,169.40999999999998948,NULL,'','zgtw','','csv','2026-05-05 14:11:10');
   454|INSERT INTO "table" VALUES('000928','中钢国际','深市','[]','专业工程',NULL,NULL,93.109999999999999431,NULL,'','zggj','','csv','2026-05-05 14:11:08');
   455|INSERT INTO "table" VALUES('000929','*ST兰黄','深市','[]','非白酒',NULL,NULL,18.969999999999998863,NULL,'','*STlh','','csv','2026-05-05 14:11:08');
   456|INSERT INTO "table" VALUES('000930','中粮科技','深市','[]','农产品加工',NULL,NULL,112.11999999999999744,NULL,'','zlkj','','csv','2026-05-05 14:11:08');
   457|INSERT INTO "table" VALUES('000931','中 关 村','深市','[]','化学制药',NULL,NULL,35.750000000000001776,NULL,'','z g c','','csv','2026-05-05 14:11:09');
   458|INSERT INTO "table" VALUES('000932','华菱钢铁','深市','[]','普钢',NULL,NULL,319.32999999999998053,NULL,'','hlgt','','csv','2026-05-05 14:11:08');
   459|INSERT INTO "table" VALUES('000933','神火股份','深市','[]','工业金属',NULL,NULL,718.27999999999994074,NULL,'','shgf','','csv','2026-05-05 14:11:08');
   460|INSERT INTO "table" VALUES('000935','四川双马','深市','[]','多元金融',NULL,NULL,209.56000000000001293,NULL,'','scsm','','csv','2026-05-05 14:11:10');
   461|INSERT INTO "table" VALUES('000936','华西股份','深市','[]','化学纤维',NULL,NULL,63.780000000000001136,NULL,'','hxgf','','csv','2026-05-05 14:11:11');
   462|INSERT INTO "table" VALUES('000937','冀中能源','深市','[]','煤炭开采',NULL,NULL,192.61000000000001008,NULL,'','jzny','','csv','2026-05-05 14:11:07');
   463|INSERT INTO "table" VALUES('000938','紫光股份','深市','[]','IT服务Ⅱ',NULL,NULL,920.94000000000004746,NULL,'','zggf','','csv','2026-05-05 14:11:10');
   464|INSERT INTO "table" VALUES('000939','凯迪退','深市','[]','--',NULL,NULL,4.5599999999999996092,NULL,'','kdt','','csv','2026-05-05 14:11:09');
   465|INSERT INTO "table" VALUES('000948','南天信息','深市','[]','软件开发',NULL,NULL,56.579999999999994741,NULL,'','ntxx','','csv','2026-05-05 14:11:10');
   466|INSERT INTO "table" VALUES('000949','新乡化纤','深市','[]','化学纤维',NULL,NULL,132.85000000000000142,NULL,'','xxhx','','csv','2026-05-05 14:11:09');
   467|INSERT INTO "table" VALUES('000950','重药控股','深市','[]','医药商业',NULL,NULL,100.75000000000000621,NULL,'','zykg','','csv','2026-05-05 14:11:07');
   468|INSERT INTO "table" VALUES('000951','中国重汽','深市','[]','商用车',NULL,NULL,260.44999999999998152,NULL,'','zgzq','','csv','2026-05-05 14:11:07');
   469|INSERT INTO "table" VALUES('000952','广济药业','深市','[]','化学制药',NULL,NULL,25.590000000000001634,NULL,'','gjyy','','csv','2026-05-05 14:11:08');
   470|INSERT INTO "table" VALUES('000953','河化股份','深市','[]','化学制药',NULL,NULL,25.670000000000001705,NULL,'','hhgf','','csv','2026-05-05 14:11:08');
   471|INSERT INTO "table" VALUES('000955','欣龙控股','深市','[]','纺织制造',NULL,NULL,28.05000000000000071,NULL,'','xlkg','','csv','2026-05-05 14:11:10');
   472|INSERT INTO "table" VALUES('000956','中原油气','深市','[]','--',NULL,NULL,30.369999999999999218,NULL,'','zyyq','','csv','2026-05-05 14:11:09');
   473|INSERT INTO "table" VALUES('000957','中通客车','深市','[]','商用车',NULL,NULL,70.909999999999993036,NULL,'','ztkc','','csv','2026-05-05 14:11:11');
   474|INSERT INTO "table" VALUES('000958','电投产融','深市','[]','电力',NULL,NULL,319.77999999999995317,NULL,'','dtcr','','csv','2026-05-05 14:11:09');
   475|INSERT INTO "table" VALUES('000959','首钢股份','深市','[]','普钢',NULL,NULL,339.05000000000002913,NULL,'','sggf','','csv','2026-05-05 14:11:07');
   476|INSERT INTO "table" VALUES('000960','锡业股份','深市','[]','小金属',NULL,NULL,581.65999999999993264,NULL,'','xygf','','csv','2026-05-05 14:11:13');
   477|INSERT INTO "table" VALUES('000961','ST中南','深市','[]','--',NULL,NULL,21.339999999999998969,NULL,'','STzn','','csv','2026-05-05 14:11:09');
   478|INSERT INTO "table" VALUES('000962','东方钽业','深市','[]','小金属',NULL,NULL,218.97999999999999687,NULL,'','dfty','','csv','2026-05-05 14:11:13');
   479|INSERT INTO "table" VALUES('000963','华东医药','深市','[]','化学制药',NULL,NULL,585.33000000000008355,NULL,'','hdyy','','csv','2026-05-05 14:11:10');
   480|INSERT INTO "table" VALUES('000965','天保基建','深市','[]','房地产开发',NULL,NULL,41.619999999999999218,NULL,'','tbjj','','csv','2026-05-05 14:11:09');
   481|INSERT INTO "table" VALUES('000966','长源电力','深市','[]','电力',NULL,NULL,149.05000000000001136,NULL,'','zydl','','csv','2026-05-05 14:11:07');
   482|INSERT INTO "table" VALUES('000967','盈峰环境','深市','[]','环保设备Ⅱ',NULL,NULL,447.82999999999999474,NULL,'','yfhj','','csv','2026-05-05 14:11:06');
   483|INSERT INTO "table" VALUES('000968','蓝焰控股','深市','[]','油气开采Ⅱ',NULL,NULL,89.299999999999997157,NULL,'','lykg','','csv','2026-05-05 14:11:07');
   484|INSERT INTO "table" VALUES('000969','安泰科技','深市','[]','金属新材料',NULL,NULL,218.7400000000000233,NULL,'','atkj','','csv','2026-05-05 14:11:07');
   485|INSERT INTO "table" VALUES('000970','中科三环','深市','[]','金属新材料',NULL,NULL,147.09999999999999076,NULL,'','zksh','','csv','2026-05-05 14:11:11');
   486|INSERT INTO "table" VALUES('000971','*ST高升','深市','[]','--',NULL,NULL,4.6600000000000001421,NULL,'','*STgs','','csv','2026-05-05 14:11:09');
   487|INSERT INTO "table" VALUES('000972','*ST中基','深市','[]','农产品加工',NULL,NULL,29.390000000000000568,NULL,'','*STzj','','csv','2026-05-05 14:11:12');
   488|INSERT INTO "table" VALUES('000973','佛塑科技','深市','[]','塑料',NULL,NULL,204.89999999999999324,NULL,'','fskj','','csv','2026-05-05 14:11:10');
   489|INSERT INTO "table" VALUES('000975','山金国际','深市','[]','贵金属',NULL,NULL,658.89999999999995239,NULL,'','sjgj','','csv','2026-05-05 14:11:11');
   490|INSERT INTO "table" VALUES('000976','*ST华铁','深市','[]','--',NULL,NULL,6.5400000000000000355,NULL,'','*STht','','csv','2026-05-05 14:11:09');
   491|INSERT INTO "table" VALUES('000977','浪潮信息','深市','[]','计算机设备',NULL,NULL,1010.0599999999999578,NULL,'','lcxx','','csv','2026-05-05 14:11:12');
   492|INSERT INTO "table" VALUES('000978','桂林旅游','深市','[]','旅游及景区',NULL,NULL,31.320000000000001172,NULL,'','glly','','csv','2026-05-05 14:11:12');
   493|INSERT INTO "table" VALUES('000979','中弘退','深市','[]','--',NULL,NULL,18.460000000000000852,NULL,'','zht','','csv','2026-05-05 14:11:09');
   494|INSERT INTO "table" VALUES('000980','众泰汽车','深市','[]','汽车零部件',NULL,NULL,127.06999999999999406,NULL,'','ztqc','','csv','2026-05-05 14:11:10');
   495|INSERT INTO "table" VALUES('000981','山子高科','深市','[]','汽车零部件',NULL,NULL,368.17000000000001946,NULL,'','szgk','','csv','2026-05-05 14:11:10');
   496|INSERT INTO "table" VALUES('000982','中银绒业','深市','[]','--',NULL,NULL,7.6699999999999999289,NULL,'','zyry','','csv','2026-05-05 14:11:09');
   497|INSERT INTO "table" VALUES('000983','山西焦煤','深市','[]','煤炭开采',NULL,NULL,396.82999999999996276,NULL,'','sxjm','','csv','2026-05-05 14:11:07');
   498|INSERT INTO "table" VALUES('000985','大庆华科','深市','[]','炼化及贸易',NULL,NULL,26.320000000000001172,NULL,'','dqhk','','csv','2026-05-05 14:11:07');
   499|INSERT INTO "table" VALUES('000987','越秀资本','深市','[]','多元金融',NULL,NULL,450.69999999999996731,NULL,'','yxzb','','csv','2026-05-05 14:11:07');
   500|INSERT INTO "table" VALUES('000988','华工科技','深市','[]','自动化设备',NULL,NULL,1177.740000000000009,NULL,'','hgkj','','csv','2026-05-05 14:11:11');
   501|

COMMIT;

-- ═══════════════════════════════════════════════════════════
-- 风控规则（16条初始规则）
-- ═══════════════════════════════════════════════════════════

BEGIN TRANSACTION;

     1|INSERT INTO risk_rules VALUES(1,'涨跌幅>5%禁止买入','追高风险控制','price','change_pct','gte','5','%','fail','追高风险，禁止买入',1,1,'2026-05-01 13:50:28','2026-05-01 13:50:28');
     2|INSERT INTO risk_rules VALUES(2,'营收增长率告警','营收同比下滑超过20%','fundamental','revenue_yoy','lt','-20','%','fail','营收大幅下滑',1,10,'2026-05-01 13:50:28','2026-05-01 13:50:28');
     3|INSERT INTO risk_rules VALUES(3,'毛利率过低','毛利率低于20%','fundamental','gross_margin','lt','20','%','warning','毛利率偏低',1,11,'2026-05-01 13:50:28','2026-05-01 13:50:28');
     4|INSERT INTO risk_rules VALUES(4,'ROE过低','ROE低于5%','fundamental','roe','lt','5','%','warning','ROE偏低，盈利质量不佳',1,12,'2026-05-01 13:50:28','2026-05-01 13:50:28');
     5|INSERT INTO risk_rules VALUES(5,'资产负债率过高','负债率超过70%','fundamental','debt_ratio','gt','70','%','warning','负债率偏高，财务风险较大',1,13,'2026-05-01 13:50:28','2026-05-01 13:50:28');
     6|INSERT INTO risk_rules VALUES(8,'日均成交额不足2亿','流动性不足','volume','avg_amount_10d','lt','2','亿','fail','流动性不足，禁止买入',1,7,'2026-05-01 13:50:28','2026-05-01 13:50:28');
     7|INSERT INTO risk_rules VALUES(9,'K线形态预警','出现看跌K线形态','kline','kline_pattern','contains','看跌','','warning','出现看跌K线形态，谨慎',1,15,'2026-05-01 13:50:28','2026-05-01 13:50:28');
     8|INSERT INTO risk_rules VALUES(10,'净利下滑超30%','净利润同比下滑超过30%','fundamental','net_profit_yoy','lt','-30','%','fail','净利润大幅下滑，风险极高',1,0,'2026-05-01 13:50:28','2026-05-01 13:50:28');
     9|INSERT INTO risk_rules VALUES(12,'MA200 多空线','价格低于MA200，长期趋势偏空','technical','ma200','>','current_price','','fail','当前价在MA200下方，长期空头',1,2,'2026-05-02 11:21:02','2026-05-02 11:21:02');
    10|INSERT INTO risk_rules VALUES(13,'RSI 超买','RSI大于70，短期超买','technical','rsi_14','>','70','','warn','',1,4,'2026-05-02 11:21:02','2026-05-02 11:21:02');
    11|INSERT INTO risk_rules VALUES(14,'RSI 超卖','RSI小于30，短期超卖','technical','rsi_14','<','30','','info','',1,5,'2026-05-02 11:21:02','2026-05-02 11:21:02');
    12|INSERT INTO risk_rules VALUES(15,'MACD 金叉','MACD DIF上穿DEA，偏多信号','technical','macd_dif','>','macd_dea','','info','',1,6,'2026-05-02 11:21:02','2026-05-02 11:21:02');
    13|INSERT INTO risk_rules VALUES(16,'MACD 死叉','MACD DIF下穿DEA，偏空信号','technical','macd_dif','<','macd_dea','','warn','',1,7,'2026-05-02 11:21:02','2026-05-02 11:21:02');
    14|INSERT INTO risk_rules VALUES(17,'均线多头排列','MA5>MA10>MA20>MA60，偏多趋势','technical','bullish_alignment','==','true','','info','',1,8,'2026-05-02 11:21:02','2026-05-02 11:21:02');
    15|INSERT INTO risk_rules VALUES(18,'PE 过高','市盈率过高，估值风险较大','fundamental','pe','>','100','','warn','',1,9,'2026-05-02 11:21:02','2026-05-02 11:21:02');
    16|INSERT INTO risk_rules VALUES(19,'PE 为负','市盈率为负，公司当前亏损','fundamental','pe','<','0','','warning','公司亏损状态买入风险较高',1,10,'2026-05-02 11:21:02','2026-05-04 14:10:26');
    17|

COMMIT;

-- ═══════════════════════════════════════════════════════════
-- 思维模型（22条初始模型）
-- ═══════════════════════════════════════════════════════════

BEGIN TRANSACTION;

     1|INSERT INTO mental_models VALUES(1,'安全边际','🛡️','投资决策','以低于内在价值的价格买入，为判断错误留出缓冲空间。格雷厄姆称为「投资的核心」','买入决策：只有当价格低于合理估值下限时才出手，确保即使判断部分错误也不会亏钱','当PE/PB处于历史低位、市场恐慌时；或当你发现一个优质公司因短期利空被错杀时','某公司内在价值100元，你等到跌到70元才买入。即使估值偏差30%，你依然不亏本金',replace('## 核心理念\n\n安全边际是价值投资的基石。它不是追求「买在最低点」，而是买在「即便错了也不会亏」的位置。\n\n## 两层含义\n1. **估值保护**：买入价 < 合理价值 × (1 - 误差率)\n2. **容错空间**：为不可预见的风险留出缓冲\n\n## 实战应用\n- 关注PB < 1.5 + PE处于历史20%分位以下\n- 现金充裕 + 负债率低 + 经营稳定 → 安全边际更厚\n- 当安全边际变薄（如涨幅过高），逐步减仓\n\n## 与A股的结合\n- **牛市陷阱**：安全边际思维在牛市中常被嘲笑，但它是防止牛市综合征的关键\n- **结构性机会**：A股板块轮动剧烈，安全边际帮你区分「贵但还能涨」vs「便宜但该跌了」','\n',char(10)),'["core","value","buy"]','2026-05-06 21:03:21');
     2|INSERT INTO mental_models VALUES(2,'能力圈','🎯','投资决策','清楚知道自己懂什么、不懂什么，只在自己能理解的领域做决策。巴菲特：「重要的是知道你的能力圈边界」','选股前先自问：我是否真正理解这家公司的商业模式、竞争壁垒和行业前景？','面对热门概念股、技术复杂的企业、或你不熟悉的行业时','彼得·林奇：只买自己日常能接触到产品/服务的公司。如果你喝了它的酸奶觉得好，比你研究3天财报更有价值',replace('## 核心理念\n\n能力圈不是固定不变的，可以逐步扩展，但关键是知道边界在哪。\n\n## 如何划定能力圈\n1. **两句话测试**：能否用两句话说清这家公司怎么赚钱？\n2. **竞争对手测试**：能说出它的前3个竞争对手及其差异吗？\n3. **5年测试**：能预见这家公司5年后大概是什么样吗？\n\n## 常见陷阱\n- 看了几篇研报就以为懂了（知道 ≠ 理解）\n- 涨了就觉得在能力圈内（幸存者偏差）\n- 「这次不一样」的心态\n\n## A股实战\n- 科技股：你真的懂芯片设计/封装/制造的差异吗？\n- 医药股：仿制药和创新药的估值逻辑完全不同\n- 周期股：你需要理解产能周期，不只是看PE低','\n',char(10)),'["core","value","selection"]','2026-05-06 21:03:21');
     3|INSERT INTO mental_models VALUES(3,'复利效应','📈','投资决策','持续的小收益通过时间积累产生指数级增长。爱因斯坦称之为「世界第八大奇迹」','关注长期持有优质资产、减少交易摩擦、让收益再投资','当你考虑频繁交易 vs 长期持有、选择成长股时','年化15%的收益，持有20年即增长16倍。频繁交易每年损耗3%收益，20年只剩约一半',replace('## 核心理念\n\n复利的关键不是单期收益率有多高，而是不间断、不亏大钱。\n\n## 三大要素\n1. **本金**：投资的基础\n2. **收益率**：长期可持续的回报率\n3. **时间**：最强的变量——越早开始，复利效果越显著\n\n## 复利的敌人\n- **回撤**：跌50%需要涨100%才能回本\n- **交易成本**：每次买卖都在消耗复利\n- **频繁换仓**：打断复利连续性\n\n## A股应用\n- 长期持有优质消费/医药龙头的复利效果显著\n- 但A股波动大，要学会在泡沫时减仓、低谷时加仓\n- 红利再投资是A股中最容易被忽视的复利来源','\n',char(10)),'["core","growth","long-term"]','2026-05-06 21:03:21');
     4|INSERT INTO mental_models VALUES(4,'机会成本','📐','投资决策','每选择A就意味着放弃B、C、D的最高收益。真正的成本不是你付了多少钱，而是你放弃了什么','持仓对比：永远问自己「如果不持有这只股票，我会买什么？那个选择比现在更好吗？」','评估是否卖出持仓、选择多个标的时','持有某股年化8%，但发现同行业的龙头股预期收益15%——持有它的机会成本是每年少赚7%',replace('## 核心理念\n\n机会成本是经济学第一课，但投资中最容易被忽略。持仓不动不是因为「它没问题」，而是因为没找到更好的替代。\n\n## 实战清单\n1. 这个仓位的机会成本是多少？（对比现金/ETF/其他个股）\n2. 如果现在是空仓，我会买入这只股票吗？\n3. 我持有它是因为看好，还是因为懒得换？\n\n## A股应用\n- 板块轮动频繁，机会成本意识帮你捕捉结构性机会\n- 弱势股补仓的机会成本可能是错失了龙头股加仓时机\n- 现金也是一种选择——在市场高估时持有现金没有机会成本','\n',char(10)),'["portfolio","sell","compare"]','2026-05-06 21:03:21');
     5|INSERT INTO mental_models VALUES(5,'第二层思维','🧠','投资决策','第一层思维看表象（「这家公司好，买它」）；第二层思维看预期差（「大家都觉得它好，所以已经price in了」）','买入前必问：市场当前的定价在反映什么预期？我的观点与市场预期有何不同？','当热门股票大涨、市场一致性预期极强时','第一层：「芯片短缺利好，买芯片股」；第二层：「市场已经给芯片股极高估值，如果短缺缓解，这些公司的盈利能力还能支撑当前估值吗？」',replace('## 核心理念\n\n投资是预期差的游戏。市场已经定价的信息不是机会；只有你发现了市场尚未反映的信息才是。\n\n## 三层递进\n1. 市场在price in什么？（共识）\n2. 我有什么不同看法？（差异）\n3. 我的差异是对的吗？（验证）\n\n## 常见错误\n- 把「看好」等同于「会涨」\n- 忽略市场已经反映的正面信息\n- 过度自信自己的差异化判断\n\n## A股实战\n- 当散户一致性看多时（如雪球热帖），恰恰要警惕\n- 当机构大幅调仓而你理解了调仓逻辑时，可能发现第二层机会\n- 利空出尽=利好，利好落地=利空，也是第二层思维的体现','\n',char(10)),'["psychology","contrarian","entry"]','2026-05-06 21:03:21');
     6|INSERT INTO mental_models VALUES(6,'二阶效应','🔄','系统思维','一个行为不仅产生直接结果（一阶），还会通过系统反馈产生间接结果（二阶）。「事情比看起来更复杂」','在板块轮动中思考资金流向的二阶效应：资金从哪流出？下一站可能去哪？','板块暴涨/暴跌时、政策出台时、市场风格切换时','降息（一阶）→ 地产股涨（二阶）→ 地产带动的产业链（家电/建材）受益（三阶）',replace('## 核心理念\n\n每个行为都会引发连锁反应，只看一阶效应会忽略真正的风险或机会。\n\n## 投资中的二阶效应\n1. **政策**：不是为了刺激，而是为了「让大家觉得会被刺激」\n2. **资金流向**：跟随资金买入（一阶）→ 更多人追随（二阶）→ 获利了结引发踩踏（三阶）\n3. **板块轮动**：A板块涨了，资金需要卖B来买A，所以B会跌\n\n## A股实战\n- 北向资金净流入≠立即买入，要考虑内资会如何应对\n- 一个板块涨停潮的二阶效应：同概念发散、龙头带动产业链\n- 监管政策的二阶效应往往比政策本身影响更大','\n',char(10)),'["system","cycle","macro"]','2026-05-06 21:03:21');
     7|INSERT INTO mental_models VALUES(7,'反馈回路','🔁','系统思维','系统中的因果关系不是线性的，而是回路式的：A影响B，B反过来影响A，形成正反馈（加速）或负反馈（稳定）','识别股价趋势中的自强化（正反馈）和均值回归（负反馈）信号','股价连续上涨/下跌时、判断趋势持续性时','股价涨 → 更多人买 → 股价继续涨 → FOMO入场（正反馈，直到耗尽）',replace('## 核心理念\n\n市场由无数正反馈和负反馈回路构成。正反馈制造趋势和泡沫，负反馈带来均值回归和稳定。\n\n## 两种回路\n- **正反馈**：上涨强化上涨 → 趋势加速 → 终将崩溃\n- **负反馈**：上涨引发卖压 → 价格回归均值 → 系统稳定\n\n## 识别信号\n| 正反馈信号 | 负反馈信号 |\n|------------|------------|\n| 成交量持续放大 | 涨多了回吐 |\n| 媒体热议 | 估值修复完成 |\n| 融资余额攀升 | 技术指标超买 |\n\n## A股应用\n- A股散户占比较高，正反馈效应更强烈（涨更猛、跌更狠）\n- 量化策略加剧了正反馈——趋势跟踪策略不断强化已有趋势\n- 识别正反馈衰竭点是择时关键','\n',char(10)),'["system","trend","cycle"]','2026-05-06 21:03:21');
     8|INSERT INTO mental_models VALUES(8,'涌现','🦅','系统思维','个体简单规则通过大量交互产生整体层面的复杂行为。个股走势简单，但市场整体行为不可预测','不从单个股票去预测大盘，而是从整体结构去理解市场状态','市场情绪分析、板块联动分析时','每只蚂蚁只是遵循简单规则，蚁群却能建出复杂蚁穴。同样，每个交易者都在各自决策，却产生了「市场情绪」这个涌现现象',replace('## 核心理念\n\n市场是一个典型的涌现系统：无数个体独立决策，却产生了整体行情、板块轮动、风格切换等宏观现象。\n\n## 投资启示\n1. **不要预测市场**：涌现系统本质不可精确预测\n2. **理解结构**：关注整体模式（涨跌比、板块分化、资金流向）而非具体点位\n3. **利用而非对抗**：当涌现模式出现时，顺势而为更有效\n\n## A股应用\n- 涨停潮是典型的涌现现象\n- 板块轮动的涌现规律：科技→消费→周期→防御\n- 市场情绪的涌现指标：涨跌比、涨停家数、连板高度','\n',char(10)),'["system","macro","complexity"]','2026-05-06 21:03:21');
     9|INSERT INTO mental_models VALUES(9,'熵增定律','⚡','系统思维','封闭系统总是从有序走向无序。企业如果不注入外部能量（创新/改革），必然走向衰败','判断企业护城河是否在被侵蚀、竞争优势是否可持久','分析长期持有的标的、判断竞争格局时','曾经的诺基亚——没有外部创新注入，系统持续熵增，最终被市场淘汰',replace('## 核心理念\n\n热力学第二定律在商业中的投射：所有系统都趋向混乱。企业需要持续「做功」才能维持秩序。\n\n## 投资应用\n1. **护城河的本质**：不是壁垒本身，而是抵抗熵增的能力\n2. **持续创新的必要性**：不进步的「价值股」终将被侵蚀\n3. **管理团队评估**：优秀的管理层是注入负熵的关键\n\n## A股实战\n- 传统行业龙头的熵增更慢（如白酒、银行）\n- 科技行业熵增速率极快——今天的护城河明天可能消失\n- 资产重组/管理层变革可能是注入负熵的信号','\n',char(10)),'["system","moat","long-term"]','2026-05-06 21:03:21');
    10|INSERT INTO mental_models VALUES(10,'反脆弱','🛡️','风险管理','有些东西在波动、冲击和混乱中不但不受损，反而受益。不仅是「扛住」波动，而是「从波动中获利」','仓位管理：你的组合在极端行情中是受益还是受损？设计「有下限无上限」的结构','市场波动加大时、不确定性高时、构建投资组合时','在投资组合中加入尾部对冲期权——如果市场平稳，损失有限；但如果暴跌，则大赚。这就是反脆弱结构',replace('## 核心理念\n\n塔勒布的「三体分类」：\n- **脆弱**：害怕波动——多数高杠杆/高负债企业\n- **坚韧**：扛住波动——优质蓝筹股\n- **反脆弱**：从波动中受益——波动率策略、危机买入\n\n## 三个策略\n1. **杠铃策略**：90%极度安全 + 10%极度风险\n2. **减少脆弱性**：识别并降低组合中的脆弱因素\n3. **利用压力**：市场恐慌时正是反脆弱者出手时机\n\n## A股实战\n- 暴跌中选加仓标的：不是所有跌的都能买，要找反脆弱的（行业景气+龙头+好价格）\n- 分散不一定是反脆弱——相关系数为1的分散是伪分散\n- 港股/A股如果相关性低，配置两者才是真反脆弱','\n',char(10)),'["risk","blackswan","tail"]','2026-05-06 21:03:21');
    11|INSERT INTO mental_models VALUES(11,'杠铃策略','🏋️','风险管理','放弃平庸的中间地带，将资产分布在两个极端：极度安全 + 极度冒险。中间地带才是真正的风险区','资产配置：90%低风险（国债/指数ETF）+ 10%高风险（期权/创投/小盘成长股）','构建投资组合、不确定市场方向时','塔勒布建议：90%的资产放在零风险的国债里，10%放在高风险高回报的投机中。中间地带的「中等风险」资产其实最危险——它们给你虚假安全感',replace('## 核心理念\n\n中间地带（「中等风险」资产）给你一种「我还好」的假象，实际上既不能带来足够的安全，也放弃了高收益的可能性。\n\n## 投资组合应用\n- **安全端**：国债、高等级债券、指数ETF、现金\n- **风险端**：个股期权、创投、小盘成长股、加密货币\n- **放弃**：中等风险的「偏股基金」「结构化理财产品」\n\n## A股实战\n- 安全端：沪深300 ETF + 高股息个股\n- 风险端：热门概念/成长股/FD期权\n- 杠铃策略的核心是两侧仓位严格分离，不发生漂移','\n',char(10)),'["risk","portfolio","allocation"]','2026-05-06 21:03:21');
    12|INSERT INTO mental_models VALUES(12,'路径依赖','🚂','风险管理','过去的决策会限制未来的选择空间，即使当前的路径不是最优的，转换成本也使得你难以改变','反省自己的持仓是否因沉没成本而舍不得卖、是否有「因为一直这么做所以继续」的惯性','持有亏损股票犹豫是否止损时、长期维持某种交易模式时','买了某股后持续下跌，但「已经亏了这么多，现在卖不就真亏了吗」——这就是路径依赖：因为过去投入而影响当下理性判断',replace('## 核心理念\n\n路径依赖是理性的敌人。沉没成本不应该影响未来决策，但人类大脑很难做到。\n\n## 三种表现\n1. **沉没成本**：因为投入了，所以不舍得放弃\n2. **惯性持仓**：因为「一直在持有」，所以继续持有\n3. **习惯性行为**：因为「上次这么做赚了」，所以这次也这么做\n\n## 打破的方法\n- **清零思维**：假设今天空仓，我会买它吗？\n- **外部视角**：如果我是一个旁观者，会怎么评价这个决策？\n- **情景测试**：如果明天停牌一年，我的决定会变吗？\n\n## A股实战\n- 套牢后一直死扛是最常见的路径依赖\n- 「价值投资」成&apos;了死扛的借口——价值投资≠不止损\n- 主动打破路径依赖：每季度重新审阅所有持仓的理由','\n',char(10)),'["risk","psychology","stop"]','2026-05-06 21:03:21');
    13|INSERT INTO mental_models VALUES(13,'黑天鹅','🦢','风险管理','具有三个特征的罕见事件：①不可预测 ②冲击巨大 ③事后人们会试图解释它本应可预测','不为不可能发生的极端事件做精确预测，而是确保组合能扛住任何黑天鹅','当市场一切平稳、波动率极低时（黑天鹅往往在大家最安心时降临）','2008年金融危机、2020年新冠疫情——每次黑天鹅前都有人说「这次不一样」',replace('## 核心理念\n\n黑天鹅不是「如果发生怎么办」，而是「什么时候发生」。关键不是预测，是做好准备。\n\n## 四个应对原则\n1. **承认无知**：我们无法预测下一次黑天鹅\n2. **减少脆弱性**：确保黑天鹅来临时你不会被摧毁（不加杠杆）\n3. **利用正向黑天鹅**：某些科技股的机会就是正向黑天鹅\n4. **别被解释欺骗**：事后大家都会说「这是显而易见的」\n\n## A股实战\n- **负向黑天鹅**：财务造假、政策突变、债务危机 → 分散配置\n- **正向黑天鹅**：技术突破、政策利好 → 保持仓位灵活\n- 最危险的时候是「一切都很好」的时候\n- 最低风险准备金：永远保留30%现金或等价物','\n',char(10)),'["risk","blackswan","tail"]','2026-05-06 21:03:21');
    14|INSERT INTO mental_models VALUES(14,'锚定效应','⚓','行为金融','人类在做判断时过度依赖最先获得的信息（「锚」），即使这个信息与当下决策无关','避免被买入价/历史高点锚定。估值应该基于当下价值，而非你当初买入的价格','持有亏损股不舍得卖（等回本）、评估当前价格贵不贵时','某股从100跌到60，你买入成本是90。现在问你60贵不贵——你心里想的是「比90便宜」，但合理估值可能是50。被买入价锚定了',replace('## 核心理念\n\n锚定效应是投资中最顽固的偏误之一。那个最初的数字会持续影响你的判断。\n\n## 常见的锚\n1. **买入价锚**：「等回本就卖」\n2. **历史高点锚**：「从高点跌了这么多，便宜了」\n3. **分析师目标价锚**：「目标价100，现在80，还有空间」\n4. **同行估值锚**：「同行业PE都是30，它25，便宜」\n\n## 破解方法\n- 不看买入价，只看当前价格与内在价值的关系\n- 用「如果明天停牌3年，我现在会买吗？」来转换视角\n- 看多个估值模型（PE/PB/DCF/历史分位），避免单一锚\n\n## A股实战\n- 「从高点跌了50%」不是买入理由\n- 「等回本」是最差的卖出理由——它和投资毫无关系\n- 每笔交易都要有独立的买/卖逻辑，不关联历史价格','\n',char(10)),'["psychology","bias","sell"]','2026-05-06 21:03:21');
    15|INSERT INTO mental_models VALUES(15,'确认偏误','🔄','行为金融','人们倾向于寻找、注意和相信那些证实自己已有信念的信息，忽视反面证据','做研究时主动寻找反面论据：列出3个「我不该买这只股票」的理由，反驳自己','买入后、持仓中不断寻找利好数据时、研究报告中','你买入某股后，只关注关于它的好消息，坏消息来了你会想「这只是短期扰动」——你正在巩固自己的判断，而不是检验它',replace('## 核心理念\n\n确认偏误是理性决策的头号杀手。它让你永远觉得自己是对的，直到市场来纠正你。\n\n## 防御机制\n1. **反向清单**：每次买卖前写3个「不应该这么做」的理由\n2. **外部视角**：如果我的朋友买了这只股票，我会怎么评价？\n3. **对抗性研究**：专门找否定你观点的文章来读\n\n## 三种场景\n- **选中时**：只看到利好，忽略风险\n- **持有中**：把每根阳线都解读为「验证了我的判断」\n- **卖出后**：如果涨了→「卖早了」；如果跌了→「卖对了」\n\n## A股实战\n- 雪球/股吧的「回声室效应」会极大强化确认偏误\n- 机构研报80%是正向的——这就是确认偏误的商业化\n- 最好的防御：建立并遵守交易系统，减少主观判断','\n',char(10)),'["psychology","bias","research"]','2026-05-06 21:03:21');
    16|INSERT INTO mental_models VALUES(16,'从众效应','🐑','行为金融','个体在群体压力下放弃独立思考，跟随大多数人的行为——即使大多数可能是错的','当所有人都在讨论某只股票时，警惕。真正的机会往往在无人问津处','热门概念炒作时、媒体报道铺天盖地时、集体看多/看空时','2020年的「茅指数」——所有人都在买核心资产，形成正反馈。但当资金耗尽，从众效应反方向发威，踩踏式下跌',replace('## 核心理念\n\n从众在进化上是有利的——在原始社会，脱离群体意味着死亡。但在投资市场，脱离群体往往是盈利的来源。\n\n## 识别从众信号\n1. **媒体密度**：同一话题连篇累牍\n2. **周边讨论**：非投资圈朋友开始谈论\n3. **情绪极端**：要么极度乐观要么极度悲观\n4. **交易拥挤**：成交量/融资余额异常放大\n\n## 应对策略\n- **逆势思考**：当所有人都看多时警惕，看空时关注\n- **但不要逆势操作**：知道大家都在买≠你就要卖，趋势可能延续\n- **等待拥挤消散**：等成交量回落后再评估\n\n## A股实战\n- A股散户比例高，从众效应更显著\n- 涨停板上的「排队买入」是极端的从众行为\n- 利用从众：在恐慌时买入（逆向），在狂热时卖出（顺势）','\n',char(10)),'["psychology","bias","crowd"]','2026-05-06 21:03:21');
    17|INSERT INTO mental_models VALUES(17,'幸存者偏差','📊','行为金融','只看到成功者（幸存者），忽略了失败者（沉默的样本），导致高估成功的概率','看研报/业绩回顾时警惕：只展示成功案例，失败案例被选择性遗忘','看到某人的投资战绩辉煌时、研究某一策略的胜率时','你看到10个靠炒股致富的故事，心想「我也行」——但你没看到那1000个亏光了的人。媒体只报道成功者',replace('## 核心理念\n\n你看到的样本不是全量样本——失败者没有得到展示的机会。这导致你高估了胜率。\n\n## 投资中的表现\n1. **策略回溯**：只看历史成功的策略，忽略失效的\n2. **大师滤镜**：巴菲特成功了就学他的方法，但和他做同样事的人99%没成功\n3. **牛股回顾**：「早知道就买了」——你只看到了涨了的，没看到那100只没涨的\n\n## 防御方法\n- 问「失败案例是怎样的？」\n- 看行业的整体成功率，而非头部案例\n- 缩小样本：在时间维度上看自己所有交易，别只记得赚的那几笔\n\n## A股实战\n- 淘股吧/雪球上的「实盘大赛」冠军有极高的幸存者偏差\n- 「一年十倍」的故事背后是上千个一年亏50%的沉默样本\n- 回测时要算上交易成本、滑点、无法成交的情况','\n',char(10)),'["psychology","bias","statistics"]','2026-05-06 21:03:21');
    18|INSERT INTO mental_models VALUES(18,'纳什均衡','♟️','博弈竞争','所有参与者都已选定最优策略，没有人可以通过单方面改变自己的策略获得更好结果','分析对手盘：如果你的对手是机构/量化基金，他们的最优策略是什么？你如何利用？','判断机构行为、分析量化策略博弈时','机构都在买同一个赛道 → 均衡被打破 → 有人先跑 → 踩踏。在均衡打破前或打破后行动，不要和人群一起行动',replace('## 核心理念\n\n每个参与者都在做对自己最有利的事，但整体结果可能对所有人都不是最优的——这就是「囚徒困境」。\n\n## 对手盘分析\n1. **机构**：大批量、流动性要求高、季度考核\n2. **游资**：快进快出、追涨杀跌、情绪驱动\n3. **量化**：策略趋同、因子拥挤、反转快\n4. **散户**：情绪化、追高杀低、反应慢\n\n## 策略\n- 识别当前市场的「均衡点」在哪里\n- 判断这个均衡是否可持续\n- 在均衡被打破前/后被动作，不要和所有人一起行动\n\n## A股实战\n- 量化基金的火爆导致「因子拥挤」——大家都用的策略会失效\n- 机构抱团是典型的纳什均衡：谁先走谁吃亏，但没人走了就要崩\n- 打破均衡的催化剂：黑天鹅、政策变化、业绩爆雷','\n',char(10)),'["game","institution","strategy"]','2026-05-06 21:03:21');
    19|INSERT INTO mental_models VALUES(19,'红皇后效应','🏃','博弈竞争','在这个世界，你必须拼命奔跑才能保持在原地。竞争越激烈，生存门槛越高','评估企业的竞争可持续性：它的竞争对手在做什么？它的优势能维持多久？','分析高竞争行业的龙头股、判断护城河深度时','智能手机行业：每年都要推出更强的芯片、更好的相机、更快的充电，只是因为「不做就落后了」——这种被迫创新就是红皇后效应',replace('## 核心理念\n\n出自《爱丽丝镜中奇遇》：红皇后说「在这里，你必须尽力奔跑才能停在原地」。在商业竞争中，进步是常态，不进步就意味着倒退。\n\n## 投资应用\n1. **高竞争行业**（科技/消费电子）：利润被持续投入研发，股东回报低\n2. **低竞争行业**（公用事业/白酒/烟草）：躺着也能赚钱\n3. **判断标准**：这家公司的护城河是否在免于红皇后效应？\n\n## A股实战\n- 锂电行业就是典型的红皇后效应——技术迭代快，产能过剩\n- 白酒不是——品牌壁垒让新进入者几乎无法挑战\n- 投资红皇后行业要买龙头（唯一幸存者），且不能长期持有\n- 投资免于红皇后效应的行业可以长期持有','\n',char(10)),'["game","moat","competition"]','2026-05-06 21:03:21');
    20|INSERT INTO mental_models VALUES(20,'生态位','🌿','博弈竞争','每个企业都有其独特的生态位——在行业中占据的特定位置和角色。找不到生态位的企业会被淘汰','找「在某个细分领域独一无二」的公司，避开「什么都做但什么都做不精」的公司','分析中小市值公司、寻找细分龙头时','一个专做汽车传感器芯片的小公司，虽然市场份额只有5%，但技术壁垒极高，高端客户离不开它——这就是一个牢固的生态位',replace('## 核心理念\n\n大自然的生态位原则：两种物种不能永久占据同一生态位。商业上，没有独特生态位的企业必然被淘汰。\n\n## 三种生态位\n1. **价格领先**（成本最低）——如格力、美的\n2. **差异化**（无可替代）——如茅台（品牌）、海天（渠道）\n3. **聚焦细分**（小而精）——专精特新\n\n## 判断方法\n- 如果这家公司明天倒闭，谁会受损？他们的损失有多大？\n- 替代这家公司的难度有多大？\n- 这家公司在行业中是否有一个独特的「没有人做得更好」的位置？\n\n## A股实战\n- 小盘股必须有清晰的生态位才值得投资\n- 「专精特新」本质就是生态位投资\n- 不要投「行业里排第四、第五」的公司——它的生态位不牢固\n- 判断生态位是否在扩大（增长）还是被侵蚀（萎缩）','\n',char(10)),'["game","moat","niche"]','2026-05-06 21:03:21');
    21|INSERT INTO mental_models VALUES(21,'创造性破坏','💥','博弈竞争','新事物通过摧毁旧事物来实现进步。旧公司的灭亡是新公司崛起的前提','投资颠覆者，而非被颠覆者。判断一个行业是否正在被技术/模式颠覆','技术变革期、传统行业升级转型时、新兴产业投资时','电动车对燃油车的颠覆、互联网对传统零售的颠覆、移动支付对银行的颠覆——每一次创造性破坏都创造了巨大的投资机会',replace('## 核心理念\n\n熊彼特的洞见：经济进步不是渐进的，而是通过「创造性的毁灭风暴」实现的。旧的结构被打破，新的结构建立。\n\n## 投资启示\n1. **辨别谁是颠覆者**：技术/模式领先，成本结构更优\n2. **识别谁将被颠覆**：商业模式脆弱、技术落后、客户流失\n3. **时机是关键**：太早进入会被「旧势力」熬死，太晚进入已错过最大涨幅\n\n## 三个信号\n- 颠覆者的产品达到主流用户的「够好用」门槛\n- 被颠覆者的利润开始下降\n- 传统龙头开始做同样的事（但他们往往太慢了）\n\n## A股实战\n- A股的创造性破坏通常来得很猛（政策+市场双重驱动）\n- 光伏行业的平价上网就是创造性破坏的典型案例\n- 投资颠覆者时不要用传统估值（PE/PB不适用）\n- 注意监管可能保护旧行业、抑制创造性破坏','\n',char(10)),'["game","innovation","disruption"]','2026-05-06 21:03:21');
    22|INSERT INTO mental_models VALUES(22,'均值回归','↩️','投资决策','极端的表现会随着时间回归平均水平。不仅是统计学规律，也是金融市场的核心力量','股价大幅偏离均线时、估值处于历史极端分位时、连续大涨/大跌后','连续大涨想追高时、连续大跌想抄底时、想判断趋势是否持续时','某PE从15倍涨到40倍（远超历史均值）→ 即使公司没变差，估值大概率会回归。反之，恐慌性暴跌到PE=8倍时，也是均值回归的机会',replace('## 核心理念\n\n均值回归不是数学必然，但在金融市场上极为普遍。人性中的贪婪和恐惧导致价格总是偏离价值，然后回归。\n\n## 适用范围\n| 强均值回归 | 弱均值回归 |\n|------------|------------|\n| PE/PB估值 | 营收增速 |\n| 情绪指标 | 利润增速 |\n| 波动率 | 市场份额 |\n| 板块相对收益 | 竞争格局 |\n\n## 实战应用\n- **超买超卖**：RSI>70或<30时，回归概率大\n- **估值分位**：PE处于历史90%分位以上 → 警惕回归\n- **板块轮动**：连续跑赢的板块可能回调，连续跑输的板块可能反弹\n\n## A股实战\n- A股的均值回归比美股更剧烈（散户情绪化导致超调）\n- 但「这次不一样」在A股也可能成立——结构性变化会改变均值\n- 牛市中的均值回归不是顶部——等出现了顶部信号再做判断\n- 均线（尤其是MA60/MA200）是均值回归的重要参考位','\n',char(10)),'["value","cycle","reversal"]','2026-05-06 21:03:21');
    23|

COMMIT;

-- ═══════════════════════════════════════════════════════════
-- 产业链数据（130条）
-- ═══════════════════════════════════════════════════════════

BEGIN TRANSACTION;

     1|INSERT INTO industry_chain VALUES('电池','{"上游-资源": ["锂矿概念"], "中游-材料": ["锂电池概念"], "下游-应用": ["新能源车", "储能概念", "充电桩"], "相关": ["固态电池", "动力电池回收"]}','2026-05-05T15:04:00','');
     2|INSERT INTO industry_chain VALUES('半导体','{"上游-设备材料": ["半导体概念", "光刻机(胶)"], "中游-设计制造": ["国产芯片", "第三代半导体"], "下游-封测应用": ["先进封装", "汽车芯片", "AI芯片"], "相关": ["存储芯片", "第四代半导体"]}','2026-05-05T15:04:00','');
     3|INSERT INTO industry_chain VALUES('汽车零部件','{"上游-原材料": ["汽车热管理", "汽车轻量化"], "中游-零部件": ["汽车零部件", "一体化压铸"], "下游-整车": ["汽车整车", "新能源汽车"], "相关": ["汽车电子", "无人驾驶"]}','2026-05-05T15:04:00','');
     4|INSERT INTO industry_chain VALUES('光伏设备','{"上游-原材料": ["硅能源", "有机硅"], "中游-电池组件": ["光伏概念", "HJT电池", "TOPCon电池"], "下游-运营": ["绿色电力"], "相关": ["储能概念", "碳中和"]}','2026-05-05T15:04:00','');
     5|INSERT INTO industry_chain VALUES('白酒','{"上游-粮食": ["农业种植"], "中游-生产": ["白酒概念"], "下游-渠道": ["新零售", "电子商务"], "相关": ["食品饮料", "大消费"]}','2026-05-05T15:04:00','');
     6|INSERT INTO industry_chain VALUES('证券','{"相关-同行": ["证券概念"], "相关-市场": ["参股券商", "互联网金融"]}','2026-05-05T15:04:00','');
     7|INSERT INTO industry_chain VALUES('医疗器械','{"上游-材料": ["医疗耗材", "生物材料"], "中游-设备": ["医疗器械概念", "体外诊断"], "下游-服务": ["医疗服务", "互联网医疗"], "相关": ["医药电商"]}','2026-05-05T15:04:00','');
     8|INSERT INTO industry_chain VALUES('软件开发','{"上游-基础设施": ["国产软件", "信创", "操作系统"], "相关-应用": ["人工智能", "数字经济", "云计算", "大数据"], "下游-行业": ["金融科技", "智慧政务"]}','2026-05-05T15:04:00','');
     9|INSERT INTO industry_chain VALUES('航空装备Ⅱ','{"上游-材料": ["军工材料"], "中游-制造": ["航空发动机", "大飞机", "军工"], "相关": ["无人机", "商业航天"]}','2026-05-05T15:04:00','');
    10|INSERT INTO industry_chain VALUES('军工电子Ⅱ','{"上游-元器件": ["军工电子", "军工信息化"], "中游-系统": ["军工", "卫星导航"], "相关": ["商业航天", "军民融合"]}','2026-05-05T15:04:00','');
    11|INSERT INTO industry_chain VALUES('自动化设备','{"上游-核心部件": ["机器人概念", "机器视觉"], "中游-整机": ["工业母机", "工业自动化"], "下游-应用": ["智能物流"], "相关": ["人形机器人"]}','2026-05-05T15:04:00','');
    12|INSERT INTO industry_chain VALUES('化学制品','{"上游-原料": ["氟化工", "磷化工", "煤化工"], "中游-生产": ["化工", "化工合成材料"], "下游-应用": ["可降解塑料", "电子化学品"], "相关": ["锂电池概念", "新材料"]}','2026-05-05T15:04:00','');
    13|INSERT INTO industry_chain VALUES('化学原料','{"上游": ["氟化工", "磷化工", "煤化工"], "中游": ["化工", "化工合成材料"], "下游": ["锂电池概念", "可降解塑料"], "相关": ["新材料"]}','2026-05-05T15:04:00','');
    14|INSERT INTO industry_chain VALUES('通信设备','{"上游-芯片": ["5G概念", "通信模组"], "中游-设备": ["通信设备", "光通信"], "下游-运营": ["电信运营", "数据中心"], "相关": ["物联网", "6G概念"]}','2026-05-05T15:04:00','');
    15|INSERT INTO industry_chain VALUES('计算机设备','{"上游-零部件": ["存储芯片", "AI芯片"], "中游-整机": ["服务器", "计算机设备"], "下游-应用": ["云计算", "数据中心"], "相关": ["信创", "国产软件"]}','2026-05-05T15:04:00','');
    16|INSERT INTO industry_chain VALUES('电力','{"上游-发电": ["绿色电力", "风电", "光伏概念"], "中游-传输": ["智能电网", "特高压"], "下游-服务": ["储能概念", "电力物联网"], "相关": ["碳中和", "充电桩"]}','2026-05-05T15:04:00','');
    17|INSERT INTO industry_chain VALUES('电子化学品Ⅱ','{"上游-原料": ["氟化工", "磷化工"], "中游-材料": ["光刻胶", "半导体材料"], "下游-应用": ["半导体", "显示面板"], "相关": ["PCB概念"]}','2026-05-05T15:04:00','');
    18|INSERT INTO industry_chain VALUES('IT服务Ⅱ','{"上游-基础设施": ["数据中心", "云计算", "国产软件"], "中游-服务": ["IT服务", "数字经济"], "下游-行业应用": ["金融科技", "智慧政务", "医疗信息化"], "相关": ["信创", "人工智能"]}','2026-05-07T15:58:35.394042','');
    19|INSERT INTO industry_chain VALUES('一般零售','{"上游-供应链": ["供应链物流", "冷链物流"], "中游-渠道": ["新零售", "电子商务"], "下游-终端": ["超市", "百货"], "相关": ["跨境电商", "免税概念"]}','2026-05-07T15:58:35.394042','');
    20|INSERT INTO industry_chain VALUES('专业工程','{"上游-材料": ["钢结构", "建筑材料"], "中游-工程": ["专业工程", "工程咨询"], "下游-运营": ["基建工程", "一带一路"], "相关": ["装配式建筑", "新型城镇化"]}','2026-05-07T15:58:35.394042','');
    21|INSERT INTO industry_chain VALUES('专业服务','{"上游-工具": ["人力资源", "企业管理"], "中游-服务": ["专业服务", "检测服务"], "下游-客户": ["企业服务", "商务咨询"], "相关": ["会展服务", "安保服务"]}','2026-05-07T15:58:35.394042','');
    22|INSERT INTO industry_chain VALUES('专业连锁Ⅱ','{"上游-供应链": ["供应链管理", "新零售"], "中游-渠道": ["新零售", "电子商务"], "下游-消费": ["消费概念", "商业百货"], "相关": ["跨境电商", "连锁经营"]}','2026-05-07T15:58:35.394042','');
    23|INSERT INTO industry_chain VALUES('专用设备','{"上游-核心部件": ["机器人概念", "机器视觉", "传感器"], "中游-整机": ["工业母机", "专用设备", "智能装备"], "下游-应用": ["智能制造", "工业自动化", "半导体设备"], "相关": ["人形机器人", "锂电池概念"]}','2026-05-07T15:58:35.394042','');
    24|INSERT INTO industry_chain VALUES('个护用品','{"上游-原料": ["日化", "化工"], "中游-生产": ["个护用品", "日化品牌"], "下游-渠道": ["新零售", "电子商务", "直播带货"], "相关": ["医美概念", "化妆品"]}','2026-05-07T15:58:35.394042','');
    25|INSERT INTO industry_chain VALUES('中药Ⅱ','{"上游-原料": ["中药概念", "中药材种植"], "中游-生产": ["中药概念", "品牌中药"], "下游-渠道": ["医药商业", "互联网医疗"], "相关": ["医保概念", "大消费"]}','2026-05-07T15:58:35.394042','');
    26|INSERT INTO industry_chain VALUES('乘用车','{"上游-零部件": ["汽车零部件", "汽车电子"], "中游-整车": ["汽车整车", "新能源车", "新能源汽车"], "下游-服务": ["充电桩", "无人驾驶", "车联网"], "相关": ["汽车热管理", "一体化压铸"]}','2026-05-07T15:58:35.394042','');
    27|INSERT INTO industry_chain VALUES('互联网电商','{"上游-技术": ["云计算", "人工智能", "大数据"], "中游-平台": ["电子商务", "互联网电商", "跨境电商"], "下游-物流": ["快递物流", "仓储物流"], "相关": ["新零售", "直播带货"]}','2026-05-07T15:58:35.394042','');
    28|INSERT INTO industry_chain VALUES('休闲食品','{"上游-原料": ["农业种植", "食品添加剂"], "中游-生产": ["食品加工", "休闲食品"], "下游-渠道": ["新零售", "电子商务", "预制菜概念"], "相关": ["大消费", "调味品"]}','2026-05-07T15:58:35.394042','');
    29|INSERT INTO industry_chain VALUES('体育Ⅱ','{"上游-装备": ["体育概念", "运动装备"], "中游-运营": ["体育赛事", "体育产业"], "下游-消费": ["户外运动", "旅游概念"], "相关": ["大消费", "国潮概念"]}','2026-05-07T15:58:35.394042','');
    30|INSERT INTO industry_chain VALUES('保险Ⅱ','{"上游-资金": ["参股保险", "金融概念"], "中游-服务": ["保险概念", "保险服务"], "下游-投资": ["资产管理", "大金融"], "相关": ["互联网金融", "养老概念"]}','2026-05-07T15:58:35.394042','');
    31|INSERT INTO industry_chain VALUES('元件','{"上游-材料": ["电子元器件", "半导体材料"], "中游-制造": ["被动元件", "MLCC概念", "PCB概念"], "下游-应用": ["消费电子", "5G通信", "汽车电子"], "相关": ["军工电子", "国产芯片"]}','2026-05-07T15:58:35.394042','');
    32|INSERT INTO industry_chain VALUES('光学光电子','{"上游-材料": ["光刻胶", "光学材料", "半导体材料"], "中游-器件": ["光学光电子", "LED概念", "显示面板"], "下游-应用": ["消费电子", "机器视觉", "安防"], "相关": ["激光概念", "元宇宙概念"]}','2026-05-07T15:58:35.394042','');
    33|INSERT INTO industry_chain VALUES('其他家电Ⅱ','{"上游-零部件": ["家电零部件", "电机"], "中游-生产": ["家电概念", "小家电"], "下游-渠道": ["新零售", "电子商务"], "相关": ["智能家居", "健康中国"]}','2026-05-07T15:58:35.394042','');
    34|INSERT INTO industry_chain VALUES('其他电子Ⅱ','{"上游-元器件": ["电子元器件", "PCB概念"], "中游-制造": ["消费电子", "苹果概念", "华为概念"], "下游-应用": ["物联网", "汽车电子", "智能穿戴"], "相关": ["军工电子", "国产芯片"]}','2026-05-07T15:58:35.394042','');
    35|INSERT INTO industry_chain VALUES('其他电源设备Ⅱ','{"上游-器件": ["电源设备", "储能概念"], "中游-系统": ["输变电设备", "智能电网"], "下游-应用": ["充电桩", "新能源车", "数据中心"], "相关": ["特高压", "风电概念"]}','2026-05-07T15:58:35.394042','');
    36|INSERT INTO industry_chain VALUES('养殖业','{"上游-饲料": ["饲料概念", "动物疫苗"], "中游-养殖": ["养殖业", "猪肉概念", "鸡肉概念"], "下游-加工": ["食品加工", "预制菜概念"], "相关": ["农业种植", "动保概念"]}','2026-05-07T15:58:35.394042','');
    37|INSERT INTO industry_chain VALUES('农业综合Ⅱ','{"上游-资源": ["农业种植", "种业概念"], "中游-服务": ["农业服务", "农机概念"], "下游-加工": ["农产品加工", "食品加工"], "相关": ["乡村振兴", "土地流转"]}','2026-05-07T15:58:35.394042','');
    38|INSERT INTO industry_chain VALUES('农产品加工','{"上游-原料": ["农业种植", "种业概念"], "中游-加工": ["农产品加工", "食品加工"], "下游-渠道": ["新零售", "预制菜概念"], "相关": ["大消费", "乡村振兴"]}','2026-05-07T15:58:35.394042','');
    39|INSERT INTO industry_chain VALUES('农化制品','{"上游-原料": ["磷化工", "氟化工", "煤化工"], "中游-生产": ["化肥概念", "农药概念", "农化制品"], "下游-应用": ["农业种植", "乡村振兴"], "相关": ["化工", "转基因"]}','2026-05-07T15:58:35.394042','');
    40|INSERT INTO industry_chain VALUES('冶钢原料','{"上游-资源": ["铁矿石", "煤炭概念"], "中游-加工": ["冶钢原料", "石墨电极"], "下游-钢铁": ["普钢", "特钢"], "相关": ["碳中和", "资源股"]}','2026-05-07T15:58:35.394042','');
    41|INSERT INTO industry_chain VALUES('出版','{"上游-内容": ["知识产权", "IP经济"], "中游-出版": ["出版概念", "文化传媒"], "下游-发行": ["数字阅读", "教育概念"], "相关": ["人工智能", "元宇宙概念"]}','2026-05-07T15:58:35.394042','');
    42|INSERT INTO industry_chain VALUES('动物保健Ⅱ','{"上游-原料": ["动物疫苗", "生物医药"], "中游-生产": ["动保概念", "动物保健"], "下游-应用": ["养殖业", "宠物经济"], "相关": ["生物制品", "农业服务"]}','2026-05-07T15:58:35.394042','');
    43|INSERT INTO industry_chain VALUES('包装印刷','{"上游-材料": ["造纸概念", "可降解塑料"], "中游-生产": ["包装印刷", "烟包概念"], "下游-应用": ["消费电子", "食品包装", "快递物流"], "相关": ["碳中和", "环保概念"]}','2026-05-07T15:58:35.394042','');
    44|INSERT INTO industry_chain VALUES('化妆品','{"上游-原料": ["日化", "化工原料", "医美原料"], "中游-品牌": ["化妆品", "医美概念", "日化品牌"], "下游-渠道": ["新零售", "电子商务", "直播带货"], "相关": ["大消费", "国潮概念"]}','2026-05-07T15:58:35.394042','');
    45|INSERT INTO industry_chain VALUES('化学制药','{"上游-原料": ["化学制药", "原料药"], "中游-研发": ["创新药", "CXO概念"], "下游-渠道": ["医药商业", "互联网医疗"], "相关": ["医保概念", "生物医药"]}','2026-05-07T15:58:35.394042','');
    46|INSERT INTO industry_chain VALUES('化学纤维','{"上游-原料": ["煤化工", "石油化工"], "中游-生产": ["化工合成材料", "化学纤维"], "下游-应用": ["纺织制造", "服装家纺", "工业丝"], "相关": ["可降解塑料", "新材料"]}','2026-05-07T15:58:35.394042','');
    47|INSERT INTO industry_chain VALUES('医疗服务','{"上游-器械": ["医疗器械概念", "医疗耗材"], "中游-服务": ["医疗服务", "互联网医疗", "民营医院"], "下游-支付": ["医保概念", "健康中国"], "相关": ["养老概念", "CXO概念"]}','2026-05-07T15:58:35.394042','');
    48|INSERT INTO industry_chain VALUES('医疗美容','{"上游-原料": ["医美原料", "玻尿酸概念"], "中游-产品": ["医美概念", "医疗器械"], "下游-服务": ["医疗服务", "民营医院", "化妆品"], "相关": ["大消费", "轻医美"]}','2026-05-07T15:58:35.394042','');
    49|INSERT INTO industry_chain VALUES('医药商业','{"上游-药企": ["化学制药", "中药概念", "生物医药"], "中游-流通": ["医药商业", "冷链物流"], "下游-终端": ["互联网医疗", "药店概念", "医保概念"], "相关": ["新零售", "大消费"]}','2026-05-07T15:58:35.394042','');
    50|INSERT INTO industry_chain VALUES('厨卫电器','{"上游-零部件": ["家电零部件", "电机"], "中游-生产": ["白色家电", "厨卫电器"], "下游-渠道": ["新零售", "电子商务"], "相关": ["智能家居", "消费概念"]}','2026-05-07T15:58:35.394042','');
    51|INSERT INTO industry_chain VALUES('商用车','{"上游-零部件": ["汽车零部件", "汽车电子"], "中游-整车": ["汽车整车", "新能源车", "燃料电池"], "下游-应用": ["物流运输", "一带一路", "基建工程"], "相关": ["无人驾驶", "车联网"]}','2026-05-07T15:58:35.394042','');
    52|INSERT INTO industry_chain VALUES('地面兵装Ⅱ','{"上游-材料": ["军工材料", "特种钢材"], "中游-装备": ["地面兵装", "军工概念", "军工电子"], "下游-系统": ["军工信息化", "军民融合"], "相关": ["航空航天", "无人机"]}','2026-05-07T15:58:35.394042','');
    53|INSERT INTO industry_chain VALUES('基础建设','{"上游-材料": ["水泥概念", "建筑材料", "钢铁"], "中游-施工": ["基础建设", "工程咨询", "建筑工程"], "下游-运营": ["一带一路", "新型城镇化", "基建工程"], "相关": ["装配式建筑", "PPP概念"]}','2026-05-07T15:58:35.394042','');
    54|INSERT INTO industry_chain VALUES('塑料','{"上游-原料": ["化工原料", "煤化工", "石油化工"], "中游-生产": ["化工合成材料", "塑料概念"], "下游-应用": ["可降解塑料", "包装印刷", "汽车零部件"], "相关": ["新材料", "碳中和"]}','2026-05-07T15:58:35.394042','');
    55|INSERT INTO industry_chain VALUES('多元金融','{"上游-资金": ["信托概念", "参股金融", "金融概念"], "中游-平台": ["多元金融", "互联网金融", "供应链金融"], "下游-服务": ["资产管理", "消费金融"], "相关": ["大金融", "券商概念"]}','2026-05-07T15:58:35.394042','');
    56|INSERT INTO industry_chain VALUES('家居用品','{"上游-材料": ["木材", "建筑材料", "化工"], "中游-生产": ["家居用品", "智能家居", "定制家居"], "下游-渠道": ["新零售", "电子商务", "精装修"], "相关": ["大消费", "房地产概念"]}','2026-05-07T15:58:35.394042','');
    57|INSERT INTO industry_chain VALUES('家电零部件Ⅱ','{"上游-材料": ["电机", "电子元器件", "磁性材料"], "中游-制造": ["家电零部件", "白色家电"], "下游-整机": ["家电概念", "智能家居"], "相关": ["机器人概念", "新能源车"]}','2026-05-07T15:58:35.394042','');
    58|INSERT INTO industry_chain VALUES('小家电','{"上游-零部件": ["家电零部件", "电机"], "中游-生产": ["小家电", "家电概念"], "下游-渠道": ["新零售", "电子商务", "直播带货"], "相关": ["智能家居", "消费概念"]}','2026-05-07T15:58:35.394042','');
    59|INSERT INTO industry_chain VALUES('小金属','{"上游-资源": ["小金属概念", "有色概念", "稀土永磁"], "中游-冶炼": ["金属新材料", "稀有金属"], "下游-应用": ["新能源车", "半导体", "军工概念"], "相关": ["资源股", "锂电池概念"]}','2026-05-07T15:58:35.394042','');
    60|INSERT INTO industry_chain VALUES('工业金属','{"上游-资源": ["铜概念", "铝概念", "锌概念"], "中游-冶炼": ["工业金属", "有色概念", "金属冶炼"], "下游-应用": ["基建工程", "新能源车", "电力设备"], "相关": ["资源股", "碳中和"]}','2026-05-07T15:58:35.394042','');
    61|INSERT INTO industry_chain VALUES('工程咨询服务Ⅱ','{"上游-技术": ["工程设计", "建筑咨询", "BIM概念"], "中游-服务": ["工程咨询", "专业服务"], "下游-项目": ["基础建设", "一带一路", "新基建"], "相关": ["新型城镇化", "智慧城市"]}','2026-05-07T15:58:35.394042','');
    62|INSERT INTO industry_chain VALUES('工程机械','{"上游-核心部件": ["液压概念", "发动机", "传感器"], "中游-整机": ["工程机械", "工业母机", "专用设备"], "下游-应用": ["基建工程", "一带一路", "新型城镇化"], "相关": ["智能制造", "工业自动化"]}','2026-05-07T15:58:35.394042','');
    63|INSERT INTO industry_chain VALUES('广告营销','{"上游-媒体": ["数字媒体", "短视频概念"], "中游-平台": ["广告营销", "互联网广告", "网红经济"], "下游-品牌": ["新零售", "电子商务", "直播带货"], "相关": ["人工智能", "元宇宙概念"]}','2026-05-07T15:58:35.394042','');
    64|INSERT INTO industry_chain VALUES('影视院线','{"上游-制作": ["影视概念", "文化传媒"], "中游-发行": ["院线概念", "电影概念", "电视剧"], "下游-平台": ["流媒体", "数字媒体", "短视频概念"], "相关": ["元宇宙概念", "IP经济"]}','2026-05-07T15:58:35.394042','');
    65|INSERT INTO industry_chain VALUES('房地产开发','{"上游-土地": ["土地流转", "新城概念"], "中游-开发": ["房地产开发", "房地产概念"], "下游-物业": ["物业管理", "商业百货", "长租公寓"], "相关": ["新型城镇化", "REITs概念"]}','2026-05-07T15:58:35.394042','');
    66|INSERT INTO industry_chain VALUES('房地产服务','{"上游-开发": ["房地产开发", "房地产概念"], "中游-服务": ["物业管理", "房地产服务"], "下游-运营": ["商业运营", "长租公寓"], "相关": ["智慧城市", "新零售"]}','2026-05-07T15:58:35.394042','');
    67|INSERT INTO industry_chain VALUES('房屋建设Ⅱ','{"上游-材料": ["建筑材料", "水泥概念", "钢结构"], "中游-施工": ["房屋建设", "建筑工程", "基础建设"], "下游-装修": ["精装修", "智能家居"], "相关": ["装配式建筑", "新型城镇化"]}','2026-05-07T15:58:35.394042','');
    68|INSERT INTO industry_chain VALUES('摩托车及其他','{"上游-零部件": ["汽车零部件", "电机"], "中游-整车": ["摩托车", "汽车整车"], "下游-服务": ["共享经济", "快递物流"], "相关": ["新能源车", "消费概念"]}','2026-05-07T15:58:35.394042','');
    69|INSERT INTO industry_chain VALUES('教育','{"上游-技术": ["云计算", "人工智能", "在线教育"], "中游-平台": ["教育概念", "在线教育", "职业教育"], "下游-评估": ["考试培训", "素质教育"], "相关": ["数字经济", "出版概念"]}','2026-05-07T15:58:35.394042','');
    70|INSERT INTO industry_chain VALUES('数字媒体','{"上游-内容": ["知识产权", "IP经济", "数字阅读"], "中游-平台": ["数字媒体", "流媒体", "短视频概念"], "下游-变现": ["广告营销", "网络游戏", "电子商务"], "相关": ["元宇宙概念", "人工智能"]}','2026-05-07T15:58:35.394042','');
    71|INSERT INTO industry_chain VALUES('文娱用品','{"上游-设计": ["IP经济", "文具概念"], "中游-生产": ["文娱用品", "玩具概念"], "下游-渠道": ["新零售", "电子商务", "直播带货"], "相关": ["大消费", "国潮概念"]}','2026-05-07T15:58:35.394042','');
    72|INSERT INTO industry_chain VALUES('旅游及景区','{"上游-交通": ["航空机场", "铁路公路", "航运港口"], "中游-服务": ["旅游概念", "旅游酒店", "景区概念"], "下游-消费": ["酒店餐饮", "免税概念", "新零售"], "相关": ["大消费", "户外运动"]}','2026-05-07T15:58:35.394042','');
    73|INSERT INTO industry_chain VALUES('旅游零售Ⅱ','{"上游-商品": ["新零售", "百货概念", "免税概念"], "中游-渠道": ["旅游零售", "跨境电商", "电子商务"], "下游-消费": ["旅游概念", "大消费", "出境游"], "相关": ["免税概念", "机场航运"]}','2026-05-07T15:58:35.394042','');
    74|INSERT INTO industry_chain VALUES('普钢','{"上游-原料": ["铁矿石", "焦炭概念", "冶钢原料"], "中游-生产": ["普钢", "钢铁概念", "热轧"], "下游-应用": ["基建工程", "房地产概念", "工程机械"], "相关": ["碳中和", "资源股"]}','2026-05-07T15:58:35.394042','');
    75|INSERT INTO industry_chain VALUES('服装家纺','{"上游-面料": ["纺织制造", "化工合成材料"], "中游-品牌": ["服装家纺", "国潮概念", "服饰概念"], "下游-渠道": ["新零售", "电子商务", "直播带货"], "相关": ["大消费", "跨境电商"]}','2026-05-07T15:58:35.394042','');
    76|INSERT INTO industry_chain VALUES('林业Ⅱ','{"上游-资源": ["林业概念", "园林概念"], "中游-采伐": ["木材概念", "林业"], "下游-加工": ["造纸概念", "家具概念", "建筑材料"], "相关": ["碳中和", "乡村振兴"]}','2026-05-07T15:58:35.394042','');
    77|INSERT INTO industry_chain VALUES('橡胶','{"上游-原料": ["化工原料", "石油化工"], "中游-生产": ["橡胶概念", "化工合成材料"], "下游-应用": ["汽车零部件", "轮胎概念", "工程机械"], "相关": ["新材料", "化工"]}','2026-05-07T15:58:35.394042','');
    78|INSERT INTO industry_chain VALUES('水泥','{"上游-原料": ["石灰石", "矿业概念"], "中游-生产": ["水泥概念", "建筑材料"], "下游-应用": ["基础建设", "房地产概念", "新型城镇化"], "相关": ["碳中和", "资源股"]}','2026-05-07T15:58:35.394042','');
    79|INSERT INTO industry_chain VALUES('汽车服务','{"上游-车源": ["汽车整车", "新能源车"], "中游-服务": ["汽车服务", "汽车金融"], "下游-售后": ["汽车后市场", "汽车零部件"], "相关": ["充电桩", "无人驾驶"]}','2026-05-07T15:58:35.394042','');
    80|INSERT INTO industry_chain VALUES('油服工程','{"上游-装备": ["油服概念", "石油装备", "专用设备"], "中游-服务": ["油服工程", "石油开采", "油田服务"], "下游-炼化": ["炼化及贸易", "石油化工"], "相关": ["天然气概念", "一带一路"]}','2026-05-07T15:58:35.394042','');
    81|INSERT INTO industry_chain VALUES('油气开采Ⅱ','{"上游-勘探": ["油气勘探", "石油开采"], "中游-开采": ["天然气概念", "石油概念"], "下游-炼化": ["炼化及贸易", "化工原料"], "相关": ["油服工程", "能源概念"]}','2026-05-07T15:58:35.394042','');
    82|INSERT INTO industry_chain VALUES('消费电子','{"上游-元器件": ["电子元器件", "半导体", "PCB概念"], "中游-制造": ["消费电子", "苹果概念", "华为概念", "智能穿戴"], "下游-应用": ["物联网", "元宇宙概念", "人工智能"], "相关": ["军工电子", "5G通信"]}','2026-05-07T15:58:35.394042','');
    83|INSERT INTO industry_chain VALUES('渔业','{"上游-养殖": ["水产养殖", "养殖业"], "中游-捕捞": ["渔业概念", "远洋捕捞"], "下游-加工": ["食品加工", "预制菜概念"], "相关": ["农业概念", "乡村振兴"]}','2026-05-07T15:58:35.394042','');
    84|INSERT INTO industry_chain VALUES('游戏Ⅱ','{"上游-技术": ["人工智能", "云计算", "元宇宙概念"], "中游-研发": ["游戏概念", "网络游戏", "手机游戏"], "下游-平台": ["数字媒体", "流媒体", "电竞概念"], "相关": ["IP经济", "文化传媒"]}','2026-05-07T15:58:35.394042','');
    85|INSERT INTO industry_chain VALUES('炼化及贸易','{"上游-原油": ["石油概念", "天然气概念"], "中游-炼化": ["炼化及贸易", "石油化工", "化工原料"], "下游-成品油": ["加油站", "化工概念"], "相关": ["油服工程", "资源股"]}','2026-05-07T15:58:35.394042','');
    86|INSERT INTO industry_chain VALUES('焦炭Ⅱ','{"上游-煤炭": ["煤炭开采", "煤炭概念"], "中游-焦化": ["焦炭概念", "煤化工"], "下游-钢铁": ["普钢", "冶钢原料", "特钢"], "相关": ["资源股", "碳中和"]}','2026-05-07T15:58:35.394042','');
    87|INSERT INTO industry_chain VALUES('煤炭开采','{"上游-资源": ["煤炭概念", "焦煤概念"], "中游-开采": ["煤炭开采", "煤化工"], "下游-应用": ["火电概念", "钢铁概念", "水泥概念"], "相关": ["资源股", "能源概念"]}','2026-05-07T15:58:35.394042','');
    88|INSERT INTO industry_chain VALUES('照明设备Ⅱ','{"上游-元器件": ["LED概念", "电子元器件"], "中游-生产": ["照明设备", "LED照明"], "下游-应用": ["智慧城市", "智能家居", "景观照明"], "相关": ["半导体", "节能环保"]}','2026-05-07T15:58:35.394042','');
    89|INSERT INTO industry_chain VALUES('燃气Ⅱ','{"上游-气源": ["天然气概念", "石油概念"], "中游-管道": ["燃气概念", "城市燃气", "管网概念"], "下游-应用": ["供热供暖", "分布式能源"], "相关": ["能源概念", "碳中和"]}','2026-05-07T15:58:35.394042','');
    90|INSERT INTO industry_chain VALUES('物流','{"上游-基础设施": ["智能物流", "仓储物流", "冷链物流"], "中游-运输": ["快递物流", "物流概念", "航运概念"], "下游-服务": ["供应链物流", "跨境电商", "新零售"], "相关": ["一带一路", "无人驾驶"]}','2026-05-07T15:58:35.394042','');
    91|INSERT INTO industry_chain VALUES('特钢Ⅱ','{"上游-原料": ["铁矿石", "冶钢原料", "镍概念"], "中游-生产": ["特钢概念", "钢铁概念", "特种钢材"], "下游-应用": ["军工概念", "航空航天", "工程机械"], "相关": ["新材料", "高端制造"]}','2026-05-07T15:58:35.394042','');
    92|INSERT INTO industry_chain VALUES('环保设备Ⅱ','{"上游-材料": ["过滤材料", "化工"], "中游-生产": ["环保设备", "专用设备"], "下游-应用": ["污水处理", "固废处理", "大气治理"], "相关": ["碳中和", "节能环保"]}','2026-05-07T15:58:35.394042','');
    93|INSERT INTO industry_chain VALUES('环境治理','{"上游-技术": ["污水处理", "固废处理", "大气治理"], "中游-服务": ["环保工程", "环境治理"], "下游-运营": ["垃圾发电", "再生资源", "碳交易"], "相关": ["碳中和", "节能环保"]}','2026-05-07T15:58:35.394042','');
    94|INSERT INTO industry_chain VALUES('玻璃玻纤','{"上游-原料": ["石英", "纯碱概念"], "中游-生产": ["玻璃概念", "玻璃玻纤", "光伏玻璃"], "下游-应用": ["光伏概念", "建筑节能", "新能源车"], "相关": ["新材料", "碳中和"]}','2026-05-07T15:58:35.394042','');
    95|INSERT INTO industry_chain VALUES('生物制品','{"上游-研发": ["生物医药", "基因概念", "CXO概念"], "中游-生产": ["生物制品", "疫苗概念", "血液制品"], "下游-应用": ["医疗服务", "健康中国"], "相关": ["创新药", "防疫概念"]}','2026-05-07T15:58:35.394042','');
    96|INSERT INTO industry_chain VALUES('电机Ⅱ','{"上游-材料": ["磁性材料", "稀土永磁", "电子元器件"], "中游-制造": ["电机概念", "机器人概念"], "下游-应用": ["新能源车", "工业自动化", "家用电器"], "相关": ["智能装备", "风电概念"]}','2026-05-07T15:58:35.394042','');
    97|INSERT INTO industry_chain VALUES('电网设备','{"上游-器件": ["输变电设备", "电力设备", "智能电网"], "中游-系统": ["电网设备", "特高压", "柔性输电"], "下游-应用": ["新能源发电", "充电桩", "储能概念"], "相关": ["碳中和", "电力物联网"]}','2026-05-07T15:58:35.394042','');
    98|INSERT INTO industry_chain VALUES('电视广播Ⅱ','{"上游-内容": ["文化传媒", "IP经济", "影视概念"], "中游-传输": ["有线电视", "广电概念", "5G通信"], "下游-终端": ["流媒体", "数字媒体", "智慧家庭"], "相关": ["物联网", "融媒体"]}','2026-05-07T15:58:35.394042','');
    99|INSERT INTO industry_chain VALUES('白色家电','{"上游-零部件": ["家电零部件", "电机", "电子元器件"], "中游-生产": ["白色家电", "家电概念"], "下游-渠道": ["新零售", "智能家居", "电子商务"], "相关": ["大消费", "消费概念"]}','2026-05-07T15:58:35.394042','');
   100|INSERT INTO industry_chain VALUES('白酒Ⅱ','{"上游-粮食": ["农业种植", "白酒概念"], "中游-生产": ["白酒概念", "品牌白酒"], "下游-渠道": ["新零售", "电子商务", "酒类概念"], "相关": ["大消费", "食品饮料"]}','2026-05-07T15:58:35.394042','');
   101|INSERT INTO industry_chain VALUES('种植业','{"上游-种子": ["种业概念", "转基因"], "中游-种植": ["农业种植", "粮食概念"], "下游-加工": ["农产品加工", "食品加工"], "相关": ["乡村振兴", "土地流转"]}','2026-05-07T15:58:35.394042','');
   102|INSERT INTO industry_chain VALUES('纺织制造','{"上游-原料": ["化工合成材料", "棉花概念", "化学纤维"], "中游-生产": ["纺织制造", "纺织服装"], "下游-品牌": ["服装家纺", "国潮概念"], "相关": ["跨境电商", "大消费"]}','2026-05-07T15:58:35.394042','');
   103|INSERT INTO industry_chain VALUES('综合Ⅱ','{"上游-多元": ["综合概念", "创投概念"], "中游-运营": ["综合企业", "多元化"], "下游-投资": ["创投概念", "资产管理"], "相关": ["金融概念", "国企改革"]}','2026-05-07T15:58:35.394042','');
   104|INSERT INTO industry_chain VALUES('能源金属','{"上游-资源": ["锂矿概念", "钴概念", "镍概念", "稀土永磁"], "中游-冶炼": ["能源金属", "有色概念", "小金属概念"], "下游-应用": ["锂电池概念", "新能源车", "储能概念"], "相关": ["资源股", "新材料"]}','2026-05-07T15:58:35.394042','');
   105|INSERT INTO industry_chain VALUES('航天装备Ⅱ','{"上游-材料": ["军工材料", "钛合金", "特种钢材"], "中游-制造": ["航天装备", "大飞机", "航空航天"], "下游-应用": ["卫星导航", "商业航天", "军工概念"], "相关": ["无人机", "军工电子"]}','2026-05-07T15:58:35.394042','');
   106|INSERT INTO industry_chain VALUES('航海装备Ⅱ','{"上游-材料": ["军工材料", "钢铁"], "中游-制造": ["航海装备", "船舶制造", "船舰"], "下游-应用": ["军工概念", "航运港口"], "相关": ["一带一路", "海洋经济"]}','2026-05-07T15:58:35.394042','');
   107|INSERT INTO industry_chain VALUES('航空机场','{"上游-飞机制造": ["大飞机", "航天装备", "航空发动机"], "中游-运输": ["航空机场", "航空运输", "民航概念"], "下游-服务": ["免税概念", "旅游概念", "机场航运"], "相关": ["物流概念", "一带一路"]}','2026-05-07T15:58:35.394042','');
   108|INSERT INTO industry_chain VALUES('航运港口','{"上游-造船": ["船舶制造", "航海装备"], "中游-运输": ["航运概念", "港口运输", "集装箱"], "下游-服务": ["物流概念", "航运港口", "一带一路"], "相关": ["海洋经济", "跨境电商"]}','2026-05-07T15:58:35.394042','');
   109|INSERT INTO industry_chain VALUES('装修建材','{"上游-原料": ["建筑材料", "玻璃玻纤", "木材"], "中游-生产": ["装修建材", "家居用品", "瓷砖"], "下游-应用": ["精装修", "房地产概念", "装配式建筑"], "相关": ["智能家居", "新型城镇化"]}','2026-05-07T15:58:35.394042','');
   110|INSERT INTO industry_chain VALUES('装修装饰Ⅱ','{"上游-材料": ["装修建材", "建筑材料"], "中游-施工": ["装修装饰", "精装修", "建筑装饰"], "下游-设计": ["智能家居", "家居用品"], "相关": ["房地产概念", "新型城镇化"]}','2026-05-07T15:58:35.394042','');
   111|INSERT INTO industry_chain VALUES('证券Ⅱ','{"上游-市场": ["证券概念", "券商概念"], "中游-服务": ["证券概念", "互联网金融"], "下游-投资": ["资产管理", "大金融"], "相关": ["参股券商", "金融科技"]}','2026-05-07T15:58:35.394042','');
   112|INSERT INTO industry_chain VALUES('调味发酵品Ⅱ','{"上游-原料": ["农业种植", "食品添加剂"], "中游-生产": ["调味品概念", "食品加工"], "下游-渠道": ["新零售", "电子商务", "预制菜概念"], "相关": ["大消费", "食品饮料"]}','2026-05-07T15:58:35.394042','');
   113|INSERT INTO industry_chain VALUES('贵金属','{"上游-资源": ["黄金概念", "白银概念", "有色概念"], "中游-冶炼": ["贵金属", "金属冶炼"], "下游-应用": ["珠宝首饰", "电子元器件", "投资金条"], "相关": ["避险概念", "资源股"]}','2026-05-07T15:58:35.394042','');
   114|INSERT INTO industry_chain VALUES('贸易Ⅱ','{"上游-货源": ["供应链管理", "跨境电商"], "中游-流通": ["贸易概念", "国际贸易"], "下游-渠道": ["新零售", "物流概念"], "相关": ["一带一路", "自贸区概念"]}','2026-05-07T15:58:35.394042','');
   115|INSERT INTO industry_chain VALUES('轨交设备Ⅱ','{"上游-零部件": ["铁路基建", "电气设备"], "中游-制造": ["轨交设备", "高铁概念", "铁路设备"], "下游-运营": ["铁路公路", "轨道交通", "一带一路"], "相关": ["PPP概念", "新基建"]}','2026-05-07T15:58:35.394042','');
   116|INSERT INTO industry_chain VALUES('通信服务','{"上游-设备": ["5G概念", "通信设备", "光通信"], "中游-运营": ["电信运营", "通信服务"], "下游-应用": ["物联网", "数据中心", "云计算"], "相关": ["6G概念", "人工智能"]}','2026-05-07T15:58:35.394042','');
   117|INSERT INTO industry_chain VALUES('通用设备','{"上游-核心件": ["轴承概念", "液压概念", "传感器"], "中游-整机": ["通用设备", "工业母机", "专用设备"], "下游-应用": ["智能制造", "工业自动化", "机器人概念"], "相关": ["智能装备", "军工概念"]}','2026-05-07T15:58:35.394042','');
   118|INSERT INTO industry_chain VALUES('造纸','{"上游-原料": ["林业概念", "废纸回收"], "中游-生产": ["造纸概念", "包装印刷"], "下游-应用": ["包装印刷", "文化传媒", "快递物流"], "相关": ["碳中和", "可降解塑料"]}','2026-05-07T15:58:35.394042','');
   119|INSERT INTO industry_chain VALUES('酒店餐饮','{"上游-物业": ["房地产概念", "商业地产"], "中游-运营": ["酒店餐饮", "旅游概念", "餐饮概念"], "下游-消费": ["旅游及景区", "大消费", "预制菜概念"], "相关": ["新零售", "文旅概念"]}','2026-05-07T15:58:35.394042','');
   120|INSERT INTO industry_chain VALUES('金属新材料','{"上游-资源": ["稀土永磁", "小金属概念", "有色概念"], "中游-加工": ["金属新材料", "磁性材料", "超导概念"], "下游-应用": ["新能源车", "军工概念", "半导体"], "相关": ["新材料", "高端制造"]}','2026-05-07T15:58:35.394042','');
   121|INSERT INTO industry_chain VALUES('铁路公路','{"上游-建设": ["铁路基建", "基础建设"], "中游-运输": ["铁路公路", "高速公路", "铁路运输"], "下游-物流": ["物流概念", "快递物流"], "相关": ["一带一路", "新基建"]}','2026-05-07T15:58:35.394042','');
   122|INSERT INTO industry_chain VALUES('银行Ⅱ','{"上游-资金": ["银行概念", "大金融"], "中游-服务": ["银行概念", "金融科技", "互联网金融"], "下游-客户": ["普惠金融", "小微金融"], "相关": ["资产管理", "数字货币"]}','2026-05-07T15:58:35.394042','');
   123|INSERT INTO industry_chain VALUES('非白酒','{"上游-原料": ["农产品加工", "粮食概念"], "中游-生产": ["啤酒概念", "葡萄酒", "黄酒概念"], "下游-渠道": ["新零售", "电子商务", "酒类概念"], "相关": ["大消费", "食品饮料"]}','2026-05-07T15:58:35.394042','');
   124|INSERT INTO industry_chain VALUES('非金属材料Ⅱ','{"上游-资源": ["萤石", "石墨概念", "石英概念"], "中游-加工": ["非金属材料", "新材料", "碳纤维"], "下游-应用": ["锂电池概念", "半导体", "新能源车"], "相关": ["建筑材料", "化工"]}','2026-05-07T15:58:35.394042','');
   125|INSERT INTO industry_chain VALUES('风电设备','{"上游-材料": ["碳纤维", "磁性材料", "钢铁"], "中游-制造": ["风电设备", "风能概念", "海上风电"], "下游-运营": ["绿色电力", "新能源发电"], "相关": ["碳中和", "电力物联网"]}','2026-05-07T15:58:35.394042','');
   126|INSERT INTO industry_chain VALUES('食品加工','{"上游-原料": ["农业种植", "养殖业", "农产品加工"], "中游-生产": ["食品加工", "预制菜概念", "食品饮料"], "下游-渠道": ["新零售", "电子商务", "直播带货"], "相关": ["大消费", "调味品"]}','2026-05-07T15:58:35.394042','');
   127|INSERT INTO industry_chain VALUES('饮料乳品','{"上游-原料": ["养殖业", "农业种植"], "中游-生产": ["乳业概念", "饮料概念", "食品饮料"], "下游-渠道": ["新零售", "电子商务", "预制菜概念"], "相关": ["大消费", "健康中国"]}','2026-05-07T15:58:35.394042','');
   128|INSERT INTO industry_chain VALUES('饰品','{"上游-材料": ["黄金概念", "有色概念"], "中游-设计": ["珠宝首饰", "饰品概念"], "下游-渠道": ["新零售", "电子商务", "直播带货"], "相关": ["大消费", "国潮概念"]}','2026-05-07T15:58:35.394042','');
   129|INSERT INTO industry_chain VALUES('饲料','{"上游-原料": ["农产品加工", "豆粕", "粮食概念"], "中游-生产": ["饲料概念", "养殖业", "动物疫苗"], "下游-应用": ["养殖业", "猪肉概念", "鸡肉概念"], "相关": ["农业概念", "动保概念"]}','2026-05-07T15:58:35.394042','');
   130|INSERT INTO industry_chain VALUES('黑色家电','{"上游-面板": ["显示面板", "LED概念", "电子元器件"], "中游-生产": ["黑色家电", "家电概念", "消费电子"], "下游-渠道": ["新零售", "电子商务", "智能家居"], "相关": ["华为概念", "OLED概念"]}','2026-05-07T15:58:35.394042','');
   131|

COMMIT;
