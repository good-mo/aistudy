/* ═══════════════════════════════════════════
 * MeterSphere 风格 Vue 前端应用逻辑
 * 基于 Vue 3 (Options API)
 * ═══════════════════════════════════════════ */
const { createApp } = Vue;

const TEST_TYPES = [
  { key: 'functional', name: '功能测试', icon: '🧪', desc: '正常流程/边界/异常' },
  { key: 'api',        name: '接口测试', icon: '🔌', desc: '请求/响应/状态码' },
  { key: 'ui',         name: 'UI 测试',  icon: '🎨', desc: '元素/交互/状态' },
  { key: 'performance',name: '性能测试', icon: '⚡', desc: '响应/吞吐/并发' },
  { key: 'security',   name: '安全测试', icon: '🔒', desc: '注入/越权/敏感信息' },
  { key: 'compatibility',name: '兼容性测试', icon: '🖥️', desc: '版本/平台/配置' },
  { key: 'reliability',name: '可靠性测试', icon: '🔧', desc: '幂等/容错/超时' },
];
const CASE_STATUS = [
  { key: 'draft', name: '草稿' }, { key: 'review', name: '评审中' },
  { key: 'approved', name: '已批准' }, { key: 'deprecated', name: '已废弃' },
];
const DEFECT_STATUS = [
  { key: 'open', name: '待处理' }, { key: 'in_progress', name: '处理中' },
  { key: 'resolved', name: '已解决' }, { key: 'closed', name: '已关闭' },
  { key: 'reopened', name: '重新打开' },
];
const SEVERITIES = [
  { key: 'blocker', name: 'Blocker' }, { key: 'critical', name: 'Critical' },
  { key: 'major', name: 'Major' }, { key: 'minor', name: 'Minor' },
];

const app = createApp({
  data() {
    return {
      activeModule: 'test',
      modules: [
        { key: 'test', name: '测试', icon: '🧪' },
        { key: 'tracking', name: '测试跟踪', icon: '📋' },
        { key: 'api', name: '接口测试', icon: '🔗' },
        { key: 'performance', name: '性能测试', icon: '⚡' },
        { key: 'ui', name: 'UI 测试', icon: '🖥️' },
      ],
      menuGroups: [
        { label: '工作台', items: [{ key: 'dashboard', name: '仪表盘', icon: '📊' }] },
        { label: '测试管理', items: [
          { key: 'generate', name: '测试生成', icon: '⚙️' },
          { key: 'cases', name: '用例库', icon: '📚' },
          { key: 'caseManagement', name: '用例高级管理', icon: '📋' },
          { key: 'apiTesting', name: '接口测试', icon: '🔗' },
          { key: 'project', name: '项目扫描', icon: '📁' },
        ]},
        { label: '质量管理', items: [
          { key: 'defects', name: '缺陷跟踪', icon: '🐛' },
          { key: 'reports', name: '报告中心', icon: '📊' },
        ]},
        { label: '测试洞察', items: [{ key: 'insights', name: '测试洞察', icon: '💡' }]},
        { label: '系统', items: [
          { key: 'projectMgmt', name: '项目管理', icon: '📦' },
          { key: 'tasks', name: '任务队列', icon: '⚡' },
        ]},
      ],
      currentPage: 'dashboard',
      currentWorkspace: '测试工作空间',
      connText: '连接中…', connClass: 'conn-connecting',

      testTypes: TEST_TYPES,
      genType: 'functional',
      genMode: 'single',
      genFilePath: '', genSource: '', projectPath: '',
      generating: false, scanning: false, execLogs: [], genResult: null, showStructured: true,
      scanResult: [], scanSummary: 0, lowcodeDesc: '', lowcoding: false, lowcodeResult: '',

      dashboardStats: [], recentCases: [], recentDefects: [],

      caseSearch: '', caseStatusFilter: '', caseTypeFilter: '', casePriorityFilter: '',
      caseList: [], caseStats: null, caseStatuses: CASE_STATUS,
      currentViewCase: null,
      newCase: { title: '', test_type: 'functional', priority: 'P1', test_code: '', source_code: '' },

      defectSearch: '', defectSeverity: '', defectStatus: '',
      defectList: [], severities: SEVERITIES, defectStatuses: DEFECT_STATUS,
      currentViewDefect: null, newDefectStatus: '',
      newDefect: { title: '', severity: 'major', file_path: '', description: '' },

      reportFormat: 'html', reportList: [],

      insightCards: [], skillPath: null,

      taskList: [],

      projectScanPath: '',

      modal: null, toast: { show: false, msg: '', type: 'info' },

      /* ══ 接口测试 ══ */
      apiTabs: [
        { key: 'definitions', name: '接口定义', icon: '📋' },
        { key: 'testCases', name: '接口用例', icon: '🧪' },
        { key: 'scenarios', name: '场景编排', icon: '🔄' },
        { key: 'mock', name: 'Mock 服务', icon: '🎭' },
        { key: 'debug', name: '接口调试', icon: '🔍' },
        { key: 'environments', name: '环境管理', icon: '🌍' },
      ],
      apiTab: 'definitions',
      apiDefSearch: '', apiDefMethod: '', apiDefProtocol: '',
      apiDefList: [], apiTestCaseList: [], scenarioList: [],
      mockServiceList: [], envList: [],
      currentViewApiDef: null, currentViewApiCase: null, currentViewScenario: null,
      newApiDef: { name: '', method: 'GET', path: '', protocol: 'HTTP', description: '', request_headers: '', request_params: '', request_body: '' },
      newApiCase: { name: '', method: 'GET', path: '', definition_id: '', request_headers: '', request_params: '', request_body: '', assertions: '', pre_scripts: '', post_scripts: '', asserts: [], variables: [] },
      newScenario: { name: '', description: '', steps: '', steps_arr: [], environment_id: '' },
      newMock: { name: '', method: 'GET', path: '', response_code: 200, response_headers: '', response_body: '', delay_ms: 0 },
      newEnv: { name: '', base_url: '', description: '', headers: '', variables: '' },
      debugMethod: 'GET', debugUrl: '', debugHeaders: '', debugParams: '',
      debugBody: '', debugResult: null, debugging: false,
      importApiFormat: 'postman', importApiData: '',
      apiCaseSearch: '', apiAssertTypes: [], apiProtocols: [],

      /* ══ 用例高级管理 ══ */
      caseMgmtTabs: [
        { key: 'mindmap', name: '脑图', icon: '🧠' },
        { key: 'importExport', name: '导入导出', icon: '📥' },
        { key: 'review', name: '评审', icon: '✅' },
        { key: 'dependencies', name: '依赖', icon: '🔗' },
        { key: 'trash', name: '回收站', icon: '🗑️' },
        { key: 'versions', name: '版本', icon: '📌' },
        { key: 'changes', name: '变更记录', icon: '📋' },
        { key: 'requirements', name: '需求关联', icon: '🎯' },
      ],
      caseMgmtTab: 'mindmap',
      mindmapData: null, exportFormat: 'excel', importFormat: 'excel', importData: '',
      dependencyList: [], trashList: [], versionList: [], changeLogList: [], requirementList: [],

      /* ══ 项目管理 ══ */
      projectList: [], newProject: { name: '', description: '', language: 'python', repo_url: '', path: '' },
    };
  },

  computed: {
    caseStatCards() {
      if (!this.caseStats) return [];
      const s = this.caseStats;
      const by = s.by_status || {};
      return [
        { key: 'total', icon: '📚', label: '总用例', value: s.total ?? '--', tone: 'accent' },
        { key: 'approved', icon: '✅', label: '已批准', value: by.approved ?? '--', tone: 'success' },
        { key: 'review', icon: '📝', label: '评审中', value: by.review ?? '--', tone: 'warning' },
        { key: 'draft', icon: '📋', label: '草稿', value: by.draft ?? '--', tone: 'muted' },
      ];
    },
  },

  methods: {
    fmtDate(ts) {
      if (!ts) return '--';
      try {
        const d = new Date(ts);
        if (isNaN(d.getTime())) return String(ts);
        const p = n => String(n).padStart(2, '0');
        return `${d.getFullYear()}-${p(d.getMonth()+1)}-${p(d.getDate())} ${p(d.getHours())}:${p(d.getMinutes())}`;
      } catch { return String(ts); }
    },
    debounce(fn, ms) {
      if (this._dbTimer) clearTimeout(this._dbTimer);
      this._dbTimer = setTimeout(() => fn(), ms);
    },
    showToast(msg, type = 'info') {
      this.toast = { show: true, msg, type };
      setTimeout(() => this.toast.show = false, 2600);
    },
    getTestTypeName(k) { return TEST_TYPES.find(t => t.key === k)?.name || k || '--'; },
    caseStatusName(k) { return CASE_STATUS.find(s => s.key === k)?.name || k || '--'; },
    caseStatusCls(k) {
      return k === 'approved' ? 'st-ok' : k === 'review' ? 'st-warn' : k === 'draft' ? 'st-muted' : 'st-err';
    },
    defectStatusName(k) { return DEFECT_STATUS.find(s => s.key === k)?.name || k || '--'; },
    sevName(k) { return SEVERITIES.find(s => s.key === k)?.name || k || '--'; },
    priorityName(k) { return k || '--'; },
    taskName(k) { return k || '--'; },
    taskCls(k) { return k === 'completed' ? 'st-ok' : k === 'failed' ? 'st-err' : 'st-warn'; },

    switchModule(key) { this.activeModule = key; },
    navigate(page) {
      this.currentPage = page;
      const loaders = {
        dashboard: () => this.loadDashboard(),
        cases: () => this.loadCases(),
        defects: () => this.loadDefects(),
        reports: () => this.loadReports(),
        tasks: () => this.loadTasks(),
        insights: () => this.loadInsights(),
        apiTesting: () => this.loadApiTesting(),
        caseManagement: () => this.loadCaseManagement(),
        projectMgmt: () => this.loadProjects(),

      };
      if (page.startsWith('api')) this.loadApiMeta();
      if (loaders[page]) loaders[page]();
    },

    async loadApiMeta() {
      try {
        const meta = await this.apiGet('/api/apitest/meta');
        this.apiAssertTypes = meta.assert_types || [];
        this.apiProtocols = meta.protocols || ['HTTP', 'TCP', 'SQL', 'DUBBO'];
      } catch (e) { /* 元数据加载失败时使用默认值 */ }
    },

    async apiGet(url) {
      const r = await fetch(url);
      const d = await r.json().catch(() => ({}));
      if (!r.ok) throw new Error(d.detail || d.error || '请求失败');
      return d;
    },
    async apiPost(url, body) {
      const r = await fetch(url, { method: 'POST', headers: { 'Content-Type': 'application/json' }, body: JSON.stringify(body) });
      const d = await r.json().catch(() => ({}));
      if (!r.ok) throw new Error(d.detail || d.error || '请求失败');
      return d;
    },
    async apiPut(url, body) {
      const r = await fetch(url, { method: 'PUT', headers: { 'Content-Type': 'application/json' }, body: JSON.stringify(body) });
      const d = await r.json().catch(() => ({}));
      if (!r.ok) throw new Error(d.detail || d.error || '请求失败');
      return d;
    },
    async apiDelete(url) {
      const r = await fetch(url, { method: 'DELETE' });
      const d = await r.json().catch(() => ({}));
      if (!r.ok) throw new Error(d.detail || d.error || '请求失败');
      return d;
    },

    connectWS() {
      const proto = location.protocol === 'https:' ? 'wss' : 'ws';
      this.ws = new WebSocket(`${proto}://${location.host}/ws/generate`);
      this.ws.onopen = () => { this.connText = '已连接'; this.connClass = 'conn-ok'; };
      this.ws.onerror = () => { this.connText = '连接失败'; this.connClass = 'conn-err'; };
      this.ws.onclose = () => { this.connText = '连接中…'; this.connClass = 'conn-connecting'; };
    },

    /* ══ 工作台 ══ */
    async loadDashboard() {
      try {
        const [cases, stats, defects] = await Promise.all([
          this.apiGet('/api/cases?limit=5'),
          this.apiGet('/api/cases/stats').catch(() => null),
          this.apiGet('/api/defects?limit=5'),
        ]);
        this.recentCases = (cases && cases.cases) || [];
        this.recentDefects = (defects && defects.defects) || defects || [];
        const s = stats || {};
        const by = s.by_status || {};
        this.dashboardStats = [
          { key: 'total', icon: '📚', label: '总用例', value: s.total ?? this.recentCases.length, detail: '全部测试用例', tone: 'accent' },
          { key: 'approved', icon: '✅', label: '已批准', value: by.approved ?? '--', detail: '可用于自动化执行', tone: 'success' },
          { key: 'open', icon: '🐛', label: '缺陷', value: this.recentDefects.length, detail: '当前缺陷数', tone: 'danger' },
          { key: 'review', icon: '📝', label: '评审中', value: by.review ?? '--', detail: '等待评审确认', tone: 'warning' },
        ];
        this.loadInsightValue();
      } catch (e) { this.showToast('加载工作台失败: ' + e.message, 'error'); }
    },
    async loadInsightValue() {
      try {
        const v = await this.apiGet('/api/insights/value');
        const value = v.value || {};
        this.insightCards = [
          { key: 'value', icon: '🏆', label: '测试价值分', value: value.value_score ?? '--', detail: '缺陷价值+覆盖率折算', tone: 'success' },
          { key: 'incidents', icon: '🚨', label: '避免线上事故', value: value.avoided_incidents ?? '--', detail: '已修复严重缺陷折算', tone: 'danger' },
          { key: 'defects', icon: '🐛', label: '发现缺陷', value: value.defect_count ?? '--', detail: '缺陷价值汇总', tone: 'accent' },
          { key: 'coverage', icon: '🛡️', label: '覆盖率', value: this.covPct(value.coverage_summary), detail: '证明该测的都测了', tone: 'warning' },
        ];
      } catch { /* 忽略 */ }
    },
    covPct(cov) {
      if (!cov) return '--';
      const v = typeof cov === 'number' ? cov : cov.avg;
      return v != null ? v + '%' : '--';
    },

    /* ══ 测试生成 ══ */
    async startGeneration() {
      if (!this.genSource && !this.genFilePath) { this.showToast('请输入源代码或文件路径', 'warning'); return; }
      this.generating = true; this.execLogs = []; this.genResult = null;
      try {
        const data = await this.apiPost('/api/generate', {
          source_code: this.genSource, file_path: this.genFilePath, test_type: this.genType,
        });
        const tr = data.test_result || {};
        this.genResult = {
          code: data.generated_tests || '',
          passed: tr.passed_count != null ? tr.passed_count : (tr.passed ? 1 : 0),
          failed: tr.failed_count != null ? tr.failed_count : (tr.failed ? 1 : 0),
          total: (data.coverage_report && data.coverage_report.total) || 0,
          coverage: data.coverage_report ? data.coverage_report.coverage_pct : null,
          structuredCases: data.structured_cases || [],
        };
        this.showStructured = true;
        this.execLogs.push('✅ 测试用例生成完成');
        this.showToast('测试用例生成成功', 'success');
      } catch (e) {
        this.execLogs.push('❌ ' + e.message);
        this.showToast('生成失败: ' + e.message, 'error');
      } finally { this.generating = false; }
    },
    async scanProject() {
      const path = this.genMode === 'project' ? this.projectPath : this.projectScanPath;
      if (!path) { this.showToast('请输入项目路径', 'warning'); return; }
      this.scanning = true;
      try {
        const data = await this.apiPost('/api/projects/scan', { project_path: path });
        const files = data.files || [];
        this.scanResult = files;
        this.scanSummary = files.length;
        this.showToast('扫描完成，共 ' + files.length + ' 个文件', 'success');
      } catch (e) { this.showToast('扫描失败: ' + e.message, 'error'); }
      finally { this.scanning = false; }
    },
    async batchGenerate() {
      if (!this.projectPath) { this.showToast('请输入项目路径', 'warning'); return; }
      this.generating = true;
      try {
        const data = await this.apiPost('/api/projects/generate?project_path=' + encodeURIComponent(this.projectPath), {});
        if (data.task_id) {
          this.execLogs.push('📦 批量生成任务已提交: ' + data.task_id);
          this.pollTask(data.task_id);
        } else {
          this.execLogs.push('📦 批量生成完成，共 ' + (data.results ? data.results.length : 0) + ' 个文件');
          this.showToast('批量生成完成', 'success');
        }
      } catch (e) { this.showToast('批量生成失败: ' + e.message, 'error'); }
      finally { this.generating = false; }
    },
    async lowcodeGenerate() {
      if (!this.lowcodeDesc) { this.showToast('请输入测试意图描述', 'warning'); return; }
      this.lowcoding = true;
      try {
        const data = await this.apiPost('/api/insights/lowcode', { description: this.lowcodeDesc });
        this.lowcodeResult = data.generated_test || data.test_code || JSON.stringify(data);
        this.showToast('低代码用例生成成功', 'success');
      } catch (e) { this.showToast('生成失败: ' + e.message, 'error'); }
      finally { this.lowcoding = false; }
    },
    async saveGeneratedCase() {
      if (!this.genResult) { this.showToast('暂无生成结果', 'warning'); return; }
      try {
        await this.apiPost('/api/cases', {
          title: this.genFilePath || 'AI 生成用例',
          source_code: this.genSource,
          test_code: this.genResult.code,
          test_type: this.genType,
          priority: 'P1', status: 'draft',
        });
        this.showToast('用例已保存', 'success');
        this.navigate('cases');
      } catch (e) { this.showToast('保存失败: ' + e.message, 'error'); }
    },

    /* ══ 任务 ══ */
    async pollTask(taskId) {
      try {
        const t = await this.apiGet('/api/tasks/' + taskId);
        this.showToast('任务状态: ' + (t.status || '--'), 'info');
      } catch (e) { this.showToast('任务查询失败', 'error'); }
    },
    async loadTasks() {
      try {
        const data = await this.apiGet('/api/tasks');
        this.taskList = (data && data.tasks) || [];
      } catch (e) { this.showToast('加载任务失败', 'error'); }
    },

    /* ══ 用例库 ══ */
    async loadCases() {
      try {
        const q = new URLSearchParams();
        if (this.caseSearch) q.set('search', this.caseSearch);
        if (this.caseStatusFilter) q.set('status', this.caseStatusFilter);
        if (this.caseTypeFilter) q.set('test_type', this.caseTypeFilter);
        if (this.casePriorityFilter) q.set('priority', this.casePriorityFilter);
        q.set('limit', '100');
        const data = await this.apiGet('/api/cases?' + q.toString());
        this.caseList = (data && data.cases) || [];
        this.loadCaseStats();
      } catch (e) { this.showToast('加载用例失败: ' + e.message, 'error'); }
    },
    async loadCaseStats() {
      try { this.caseStats = await this.apiGet('/api/cases/stats'); } catch { /* 忽略 */ }
    },
    openCreateCase() {
      this.newCase = { title: '', test_type: 'functional', priority: 'P1', test_code: '', source_code: '' };
      this.modal = { type: 'createCase', title: '新建用例' };
    },
    async submitModal() {
      try {
        if (this.modal.type === 'createCase') {
          if (!this.newCase.title) { this.showToast('请填写用例名称', 'warning'); return; }
          await this.apiPost('/api/cases', this.newCase);
          this.showToast('用例创建成功', 'success');
        } else if (this.modal.type === 'createDefect') {
          if (!this.newDefect.title) { this.showToast('请填写缺陷标题', 'warning'); return; }
          await this.apiPost('/api/defects', this.newDefect);
          this.showToast('缺陷创建成功', 'success');
        } else if (this.modal.type === 'changeDefect' && this.currentViewDefect) {
          await this.apiPut('/api/defects/' + this.currentViewDefect.id, { status: this.newDefectStatus });
          this.showToast('缺陷状态已更新', 'success');
        } else if (this.modal.type === 'createApiDef') {
          if (!this.newApiDef.name) { this.showToast('请填写接口名称', 'warning'); return; }
          if (!this.newApiDef.path) { this.showToast('请填写接口路径', 'warning'); return; }
          const payload = {
            name: this.newApiDef.name, method: this.newApiDef.method, path: this.newApiDef.path,
            protocol: this.newApiDef.protocol, description: this.newApiDef.description || '',
            request_headers: this.newApiDef.request_headers ? JSON.parse(this.newApiDef.request_headers) : {},
            request_params: this.newApiDef.request_params ? JSON.parse(this.newApiDef.request_params) : {},
            request_body: this.newApiDef.request_body || '',
          };
          if (this.modal.editing) {
            await this.apiPut('/api/api-definitions/' + this.modal.editing, payload);
            this.showToast('接口定义已更新', 'success');
          } else {
            await this.apiPost('/api/api-definitions', payload);
            this.showToast('接口定义创建成功', 'success');
          }
          this.loadApiDefs();
        } else if (this.modal.type === 'createApiCase') {
          if (!this.newApiCase.name) { this.showToast('请填写用例名称', 'warning'); return; }
          const payload = {
            name: this.newApiCase.name, method: this.newApiCase.method,
            path: this.newApiCase.path || '/',
            definition_id: this.newApiCase.definition_id || null,
            request_headers: this.newApiCase.request_headers ? JSON.parse(this.newApiCase.request_headers) : {},
            request_params: this.newApiCase.request_params ? JSON.parse(this.newApiCase.request_params) : {},
            request_body: this.newApiCase.request_body || '',
            assertions: this.newApiCase.assertions ? JSON.parse(this.newApiCase.assertions) : [],
            pre_scripts: this.newApiCase.pre_scripts ? JSON.parse(this.newApiCase.pre_scripts) : [],
            post_scripts: this.newApiCase.post_scripts ? JSON.parse(this.newApiCase.post_scripts) : [],
          };
          if (this.modal.editing) {
            await this.apiPut('/api/api-test-cases/' + this.modal.editing, payload);
            this.showToast('接口用例已更新', 'success');
          } else {
            await this.apiPost('/api/api-test-cases', payload);
            this.showToast('接口用例创建成功', 'success');
          }
          this.loadApiTestCases();
        } else if (this.modal.type === 'createScenario') {
          if (!this.newScenario.name) { this.showToast('请填写场景名称', 'warning'); return; }
          const payload = {
            name: this.newScenario.name,
            description: this.newScenario.description || '',
            steps: this.newScenario.steps ? JSON.parse(this.newScenario.steps) : [],
            environment_id: this.newScenario.environment_id || null,
          };
          if (this.modal.editing) {
            await this.apiPut('/api/scenarios/' + this.modal.editing, payload);
            this.showToast('场景已更新', 'success');
          } else {
            await this.apiPost('/api/scenarios', payload);
            this.showToast('场景创建成功', 'success');
          }
          this.loadScenarios();
        } else if (this.modal.type === 'createMock') {
          if (!this.newMock.name) { this.showToast('请填写 Mock 名称', 'warning'); return; }
          if (!this.newMock.path) { this.showToast('请填写 Mock 路径', 'warning'); return; }
          const payload = {
            name: this.newMock.name, method: this.newMock.method, path: this.newMock.path,
            response_code: Number(this.newMock.response_code) || 200,
            response_headers: this.newMock.response_headers ? JSON.parse(this.newMock.response_headers) : {},
            response_body: this.newMock.response_body || '{}',
            delay_ms: Number(this.newMock.delay_ms) || 0,
          };
          if (this.modal.editing) {
            await this.apiPut('/api/mock-services/' + this.modal.editing, payload);
            this.showToast('Mock 服务已更新', 'success');
          } else {
            await this.apiPost('/api/mock-services', payload);
            this.showToast('Mock 服务创建成功', 'success');
          }
          this.loadMockServices();
        } else if (this.modal.type === 'createEnv') {
          if (!this.newEnv.name) { this.showToast('请填写环境名称', 'warning'); return; }
          const payload = {
            name: this.newEnv.name, base_url: this.newEnv.base_url || '',
            description: this.newEnv.description || '',
            headers: this.newEnv.headers ? JSON.parse(this.newEnv.headers) : {},
            variables: this.newEnv.variables ? JSON.parse(this.newEnv.variables) : {},
          };
          if (this.modal.editing) {
            await this.apiPut('/api/environments/' + this.modal.editing, payload);
            this.showToast('环境已更新', 'success');
          } else {
            await this.apiPost('/api/environments', payload);
            this.showToast('环境创建成功', 'success');
          }
          this.loadEnvironments();
        } else if (this.modal.type === 'createProject') {
          if (!this.newProject.name) { this.showToast('请填写项目名称', 'warning'); return; }
          if (this.modal.editing) {
            await this.apiPut('/api/projects/' + this.modal.editing, this.newProject);
            this.showToast('项目已更新', 'success');
          } else {
            await this.apiPost('/api/projects', this.newProject);
            this.showToast('项目创建成功', 'success');
          }
          this.loadProjects();
        } else if (this.modal.type === 'importApi') {
          if (!this.importApiData) { this.showToast('请粘贴导入数据', 'warning'); return; }
          const data = JSON.parse(this.importApiData);
          const result = await this.apiPost('/api/api-definitions/import', {
            format: this.importApiFormat, data,
          });
          this.showToast('导入成功，共 ' + (result.imported || 0) + ' 个接口', 'success');
          this.loadApiDefs();
        }
        this.closeModal();
        if (this.currentPage === 'apiTesting' && this.apiTab === 'definitions') this.loadApiDefs();
        else if (this.currentPage === 'apiTesting' && this.apiTab === 'testCases') this.loadApiTestCases();
        else if (this.currentPage === 'apiTesting' && this.apiTab === 'scenarios') this.loadScenarios();
        else if (this.currentPage === 'apiTesting' && this.apiTab === 'mock') this.loadMockServices();
        else if (this.currentPage === 'apiTesting' && this.apiTab === 'environments') this.loadEnvironments();
        else this.navigate(this.currentPage);
      } catch (e) { this.showToast('操作失败: ' + e.message, 'error'); }
    },
    viewCase(c) { this.currentViewCase = c; this.modal = { type: 'viewCase', title: '用例详情' }; },
    async deleteCase(c) {
      if (!confirm('确认删除用例「' + (c.title || c.name) + '」？')) return;
      try { await this.apiDelete('/api/cases/' + c.id); this.showToast('删除成功', 'success'); this.loadCases(); }
      catch (e) { this.showToast('删除失败: ' + e.message, 'error'); }
    },

    /* ══ 缺陷 ══ */
    async loadDefects() {
      try {
        const q = new URLSearchParams();
        if (this.defectSearch) q.set('search', this.defectSearch);
        if (this.defectSeverity) q.set('severity', this.defectSeverity);
        if (this.defectStatus) q.set('status', this.defectStatus);
        q.set('limit', '100');
        const data = await this.apiGet('/api/defects?' + q.toString());
        this.defectList = Array.isArray(data) ? data : (data.defects || []);
      } catch (e) { this.showToast('加载缺陷失败: ' + e.message, 'error'); }
    },
    openCreateDefect() {
      this.newDefect = { title: '', severity: 'major', file_path: '', description: '' };
      this.modal = { type: 'createDefect', title: '新建缺陷' };
    },
    viewDefect(d) { this.currentViewDefect = d; this.modal = { type: 'viewDefect', title: '缺陷详情' }; },
    updateDefectStatus(d) {
      this.currentViewDefect = d; this.newDefectStatus = d.status;
      this.modal = { type: 'changeDefect', title: '变更缺陷状态' };
    },

    /* ══ 报告 ══ */
    async generateReport() {
      try {
        await this.apiPost('/api/reports/generate', { format: this.reportFormat });
        this.showToast('报告生成成功', 'success');
        this.loadReports();
      } catch (e) { this.showToast('报告生成失败: ' + e.message, 'error'); }
    },
    async loadReports() {
      try {
        const data = await this.apiGet('/api/reports/list');
        this.reportList = (data && data.reports) || [];
      } catch (e) { this.showToast('加载报告失败', 'error'); }
    },
    downloadReport(name) {
      window.open('/api/reports/download/' + encodeURIComponent(name), '_blank');
    },

    /* ══ 洞察 ══ */
    async loadInsights() {
      try {
        const [value, risk, skill] = await Promise.all([
          this.apiGet('/api/insights/value').catch(() => null),
          this.apiGet('/api/insights/risk').catch(() => null),
          this.apiGet('/api/insights/skill-path').catch(() => null),
        ]);
        const v = (value && value.value) || {};
        this.insightCards = [
          { key: 'value', icon: '🏆', label: '测试价值分', value: v.value_score ?? '--', detail: '缺陷价值 + 覆盖率折算', tone: 'success' },
          { key: 'incidents', icon: '🚨', label: '避免线上事故', value: v.avoided_incidents ?? '--', detail: '已修复严重缺陷折算', tone: 'danger' },
          { key: 'coverage', icon: '🛡️', label: '覆盖率', value: this.covPct(v.coverage_summary), detail: '证明该测的都测了', tone: 'accent' },
          { key: 'risk', icon: '⚠️', label: '高风险模块', value: (risk && risk.high_risk) ? risk.high_risk.length : '--', detail: '建议优先回归', tone: 'warning' },
        ];
        const ladder = (skill && skill.ladder) || {};
        this.skillPath = Object.keys(ladder).map(k => ({
          name: ladder[k].name, desc: ladder[k].desc,
          tools: (ladder[k].platform_tools || []).join(' · '),
        }));
      } catch (e) { this.showToast('加载洞察失败', 'error'); }
    },

    /* ══ 接口测试 ══ */
    async loadApiTesting() {
      await Promise.all([this.loadApiDefs(), this.loadApiTestCases(), this.loadScenarios(), this.loadMockServices(), this.loadEnvironments()]);
    },
    async loadApiDefs() {
      try {
        const q = new URLSearchParams();
        if (this.apiDefSearch) q.set('search', this.apiDefSearch);
        if (this.apiDefMethod) q.set('method', this.apiDefMethod);
        if (this.apiDefProtocol) q.set('protocol', this.apiDefProtocol);
        q.set('limit', '100');
        const data = await this.apiGet('/api/api-definitions?' + q.toString());
        this.apiDefList = (data && data.definitions) || [];
      } catch (e) { this.showToast('加载接口定义失败: ' + e.message, 'error'); }
    },
    async loadApiTestCases() {
      try {
        const q = new URLSearchParams();
        if (this.apiCaseSearch) q.set('search', this.apiCaseSearch);
        q.set('limit', '100');
        const data = await this.apiGet('/api/api-test-cases?' + q.toString());
        this.apiTestCaseList = (data && data.cases) || [];
      } catch (e) { this.showToast('加载接口用例失败: ' + e.message, 'error'); }
    },
    async loadScenarios() {
      try {
        const data = await this.apiGet('/api/scenarios');
        this.scenarioList = (data && data.scenarios) || [];
      } catch (e) { this.showToast('加载场景失败: ' + e.message, 'error'); }
    },
    async loadMockServices() {
      try {
        const data = await this.apiGet('/api/mock-services');
        this.mockServiceList = (data && data.services) || [];
      } catch (e) { this.showToast('加载 Mock 服务失败: ' + e.message, 'error'); }
    },
    async loadEnvironments() {
      try {
        const data = await this.apiGet('/api/environments');
        this.envList = (data && data.environments) || [];
      } catch (e) { this.showToast('加载环境失败: ' + e.message, 'error'); }
    },
    switchApiTab(tab) {
      this.apiTab = tab;
      if (tab === 'definitions') this.loadApiDefs();
      if (tab === 'testCases') this.loadApiTestCases();
      if (tab === 'scenarios') this.loadScenarios();
      if (tab === 'mock') this.loadMockServices();
      if (tab === 'environments') this.loadEnvironments();
    },
    openCreateApiDef() {
      this.newApiDef = { name: '', method: 'GET', path: '', protocol: 'HTTP', description: '', request_headers: '', request_params: '', request_body: '' };
      this.modal = { type: 'createApiDef', title: '新建接口定义' };
    },
    viewApiDef(d) {
      this.currentViewApiDef = d;
      this.modal = { type: 'viewApiDef', title: '接口定义详情' };
    },
    editApiDef(d) {
      this.newApiDef = {
        name: d.name, method: d.method, path: d.path, protocol: d.protocol,
        description: d.description || '',
        request_headers: JSON.stringify(d.request_headers || {}),
        request_params: JSON.stringify(d.request_params || {}),
        request_body: d.request_body || '',
      };
      this.modal = { type: 'createApiDef', title: '编辑接口定义', editing: d.id };
    },
    async deleteApiDef(d) {
      if (!confirm('确认删除接口定义「' + d.name + '」？')) return;
      try {
        await this.apiDelete('/api/api-definitions/' + d.id);
        this.showToast('删除成功', 'success');
        this.loadApiDefs();
      } catch (e) { this.showToast('删除失败: ' + e.message, 'error'); }
    },
    openCreateApiCase() {
      this.newApiCase = { name: '', method: 'GET', path: '', definition_id: '', request_headers: '', request_params: '', request_body: '', assertions: '', pre_scripts: '', post_scripts: '', asserts: [], variables: [] };
      this.modal = { type: 'createApiCase', title: '新建接口用例' };
    },
    viewApiCase(c) {
      this.currentViewApiCase = c;
      this.modal = { type: 'viewApiCase', title: '接口用例详情' };
    },
    editApiCase(c) {
      this.newApiCase = {
        name: c.name, method: c.method, path: c.path, definition_id: c.definition_id || '',
        request_headers: JSON.stringify(c.request_headers || {}),
        request_params: JSON.stringify(c.request_params || {}),
        request_body: c.request_body || '',
        assertions: JSON.stringify(c.assertions || []),
        pre_scripts: JSON.stringify(c.pre_scripts || []),
        post_scripts: JSON.stringify(c.post_scripts || []),
      };
      this.modal = { type: 'createApiCase', title: '编辑接口用例', editing: c.id };
    },
    async deleteApiCase(c) {
      if (!confirm('确认删除接口用例「' + c.name + '」？')) return;
      try {
        await this.apiDelete('/api/api-test-cases/' + c.id);
        this.showToast('删除成功', 'success');
        this.loadApiTestCases();
      } catch (e) { this.showToast('删除失败: ' + e.message, 'error'); }
    },
    debugApiCase(c) {
      this.apiTab = 'debug';
      this.debugMethod = c.method;
      this.debugUrl = c.path;
      this.debugHeaders = JSON.stringify(c.request_headers || {});
      this.debugParams = JSON.stringify(c.request_params || {});
      this.debugBody = c.request_body || '';
    },
    openCreateScenario() {
      this.newScenario = { name: '', description: '', steps: '', steps_arr: [], environment_id: '' };
      this.modal = { type: 'createScenario', title: '新建场景' };
    },
    viewScenario(s) {
      this.currentViewScenario = s;
      this.modal = { type: 'viewScenario', title: '场景详情' };
    },
    async executeScenario(s) {
      try {
        const result = await this.apiPost('/api/scenarios/' + s.id + '/execute', {});
        this.showToast('场景执行: ' + (result.success ? '全部通过' : '有失败'), result.success ? 'success' : 'error');
      } catch (e) { this.showToast('场景执行失败: ' + e.message, 'error'); }
    },
    async deleteScenario(s) {
      if (!confirm('确认删除场景「' + s.name + '」？')) return;
      try {
        await this.apiDelete('/api/scenarios/' + s.id);
        this.showToast('删除成功', 'success');
        this.loadScenarios();
      } catch (e) { this.showToast('删除失败: ' + e.message, 'error'); }
    },
    openCreateMock() {
      this.newMock = { name: '', method: 'GET', path: '', response_code: 200, response_headers: '', response_body: '', delay_ms: 0 };
      this.modal = { type: 'createMock', title: '新建 Mock 服务' };
    },
    editMockService(m) {
      this.newMock = {
        name: m.name, method: m.method, path: m.path,
        response_code: m.response_code,
        response_headers: JSON.stringify(m.response_headers || {}),
        response_body: typeof m.response_body === 'string' ? m.response_body : JSON.stringify(m.response_body),
        delay_ms: m.delay_ms || 0,
      };
      this.modal = { type: 'createMock', title: '编辑 Mock 服务', editing: m.id };
    },
    async deleteMockService(m) {
      if (!confirm('确认删除 Mock 服务「' + m.name + '」？')) return;
      try {
        await this.apiDelete('/api/mock-services/' + m.id);
        this.showToast('删除成功', 'success');
        this.loadMockServices();
      } catch (e) { this.showToast('删除失败: ' + e.message, 'error'); }
    },
    openCreateEnv() {
      this.newEnv = { name: '', base_url: '', description: '', headers: '', variables: '' };
      this.modal = { type: 'createEnv', title: '新建环境' };
    },
    editEnv(e) {
      this.newEnv = {
        name: e.name, base_url: e.base_url, description: e.description || '',
        headers: JSON.stringify(e.headers || {}), variables: JSON.stringify(e.variables || {}),
      };
      this.modal = { type: 'createEnv', title: '编辑环境', editing: e.id };
    },
    async deleteEnv(e) {
      if (!confirm('确认删除环境「' + e.name + '」？')) return;
      try {
        await this.apiDelete('/api/environments/' + e.id);
        this.showToast('删除成功', 'success');
        this.loadEnvironments();
      } catch (err) { this.showToast('删除失败: ' + err.message, 'error'); }
    },
    async runDebug() {
      if (!this.debugUrl) { this.showToast('请输入请求 URL', 'warning'); return; }
      this.debugging = true;
      try {
        let headers = {}, params = {};
        try { headers = this.debugHeaders ? JSON.parse(this.debugHeaders) : {}; } catch { this.showToast('请求头 JSON 格式错误', 'warning'); this.debugging = false; return; }
        try { params = this.debugParams ? JSON.parse(this.debugParams) : {}; } catch { this.showToast('请求参数 JSON 格式错误', 'warning'); this.debugging = false; return; }
        this.debugResult = await this.apiPost('/api/debug', {
          method: this.debugMethod, url: this.debugUrl,
          headers, params, body: this.debugBody, body_type: 'json',
        });
        this.showToast(this.debugResult.success ? '调试成功' : '调试失败', this.debugResult.success ? 'success' : 'error');
      } catch (e) { this.showToast('调试失败: ' + e.message, 'error'); }
      finally { this.debugging = false; }
    },
    async openImportApi() {
      this.importApiData = '';
      this.modal = { type: 'importApi', title: '导入接口定义' };
    },
    apiCaseStatusName(k) { return { draft: '草稿', approved: '已批准', deprecated: '已废弃' }[k] || k || '--'; },
    getApiCaseName(id) {
      const c = this.apiTestCaseList.find(c => c.id === id);
      return c ? c.name : '--';
    },

    /* ══ 用例高级管理 ══ */
    switchCaseMgmtTab(tab) {
      this.caseMgmtTab = tab;
      this.loadCaseManagement();
    },
    async loadCaseManagement() {
      if (this.caseMgmtTab === 'mindmap') await this.loadMindmap();
      if (this.caseMgmtTab === 'review') await this.loadCases();
      if (this.caseMgmtTab === 'dependencies') await this.loadDependencies();
      if (this.caseMgmtTab === 'trash') await this.loadTrash();
      if (this.caseMgmtTab === 'versions') await this.loadVersions();
      if (this.caseMgmtTab === 'changes') await this.loadChangeLogs();
      if (this.caseMgmtTab === 'requirements') await this.loadRequirements();
    },
    async loadMindmap() {
      try {
        this.mindmapData = await this.apiGet('/api/cases/mindmap');
      } catch (e) { this.showToast('加载脑图失败: ' + e.message, 'error'); }
    },
    async exportCases() {
      try {
        window.open('/api/cases/export?format=' + this.exportFormat, '_blank');
      } catch (e) { this.showToast('导出失败: ' + e.message, 'error'); }
    },
    async importCases() {
      if (!this.importData) { this.showToast('请输入要导入的数据', 'warning'); return; }
      try {
        const content = this.importFormat === 'excel' ? this.importData : JSON.stringify(JSON.parse(this.importData));
        const result = await this.apiPost('/api/cases/import', { format: this.importFormat, content, operator: 'tester' });
        const count = result.imported || result.total || result.count || 0;
        this.showToast('导入成功，共 ' + count + ' 条', 'success');
        this.loadCases();
      } catch (e) { this.showToast('导入失败: ' + e.message, 'error'); }
    },
    async submitCaseReview(c) {
      try {
        await this.apiPost('/api/cases/' + c.id + '/reviews/submit', { reviewer: 'tester', comment: '提交评审' });
        this.showToast('已提交评审', 'success');
        this.loadCases();
      } catch (e) { this.showToast('操作失败: ' + e.message, 'error'); }
    },
    async approveCaseReview(c) {
      try {
        await this.apiPost('/api/cases/' + c.id + '/reviews/approve', { reviewer: 'tester', comment: '评审通过' });
        this.showToast('评审已通过', 'success');
        this.loadCases();
      } catch (e) { this.showToast('操作失败: ' + e.message, 'error'); }
    },
    async rejectCaseReview(c) {
      try {
        await this.apiPost('/api/cases/' + c.id + '/reviews/reject', { reviewer: 'tester', comment: '评审驳回' });
        this.showToast('评审已驳回', 'success');
        this.loadCases();
      } catch (e) { this.showToast('操作失败: ' + e.message, 'error'); }
    },
    async loadDependencies() {
      try {
        const data = await this.apiGet('/api/cases?limit=100');
        const cases = (data && data.cases) || [];
        const allDeps = [];
        for (const c of cases) {
          try {
            const resp = await this.apiGet('/api/cases/' + c.id + '/dependencies');
            const deps = (resp && resp.dependencies) || [];
            for (const d of deps) {
              allDeps.push({ ...d, case_title: c.title });
            }
          } catch {}
        }
        this.dependencyList = allDeps;
      } catch (e) { this.showToast('加载依赖失败: ' + e.message, 'error'); }
    },
    async loadTrash() {
      try {
        const data = await this.apiGet('/api/cases/trash');
        this.trashList = (data && data.trash) || [];
      } catch (e) { this.showToast('加载回收站失败: ' + e.message, 'error'); }
    },
    async restoreCase(c) {
      try {
        await this.apiPost('/api/cases/' + c.id + '/restore', { operator: 'tester' });
        this.showToast('用例已恢复', 'success');
        this.loadTrash();
      } catch (e) { this.showToast('恢复失败: ' + e.message, 'error'); }
    },
    async purgeCase(c) {
      if (!confirm('确认彻底删除用例「' + c.title + '」？此操作不可恢复！')) return;
      try {
        await this.apiDelete('/api/cases/' + c.id + '/purge');
        this.showToast('用例已彻底删除', 'success');
        this.loadTrash();
      } catch (e) { this.showToast('删除失败: ' + e.message, 'error'); }
    },
    async loadVersions() {
      try {
        const data = await this.apiGet('/api/cases?limit=100');
        const cases = (data && data.cases) || [];
        const allVersions = [];
        for (const c of cases) {
          try {
            const resp = await this.apiGet('/api/cases/' + c.id + '/versions');
            const vers = (resp && resp.versions) || [];
            for (const v of vers) {
              allVersions.push({ ...v, case_title: c.title });
            }
          } catch {}
        }
        this.versionList = allVersions;
      } catch (e) { this.showToast('加载版本失败: ' + e.message, 'error'); }
    },
    async rollbackCaseVersion(v) {
      if (!confirm('确认回滚到该版本？')) return;
      try {
        await this.apiPost('/api/cases/' + v.case_id + '/rollback', { version: v.version });
        this.showToast('版本已回滚', 'success');
        this.loadVersions();
      } catch (e) { this.showToast('回滚失败: ' + e.message, 'error'); }
    },
    async loadChangeLogs() {
      try {
        const data = await this.apiGet('/api/cases?limit=100');
        const cases = (data && data.cases) || [];
        const allLogs = [];
        for (const c of cases) {
          try {
            const resp = await this.apiGet('/api/cases/' + c.id + '/changes');
            const logs = (resp && resp.changes) || [];
            for (const l of logs) {
              allLogs.push({ ...l, case_title: c.title });
            }
          } catch {}
        }
        this.changeLogList = allLogs;
      } catch (e) { this.showToast('加载变更记录失败: ' + e.message, 'error'); }
    },
    changeActionName(a) {
      const map = { created: '创建', updated: '更新', deleted: '删除', restored: '恢复',
        version_created: '版本创建', version_rolled_back: '版本回滚',
        review_submitted: '提交评审', review_approved: '评审通过', review_rejected: '评审驳回',
        imported: '导入', exported: '导出' };
      return map[a] || a || '--';
    },
    async loadRequirements() {
      try {
        const data = await this.apiGet('/api/cases?limit=100');
        const cases = (data && data.cases) || [];
        const allReqs = [];
        for (const c of cases) {
          try {
            const resp = await this.apiGet('/api/cases/' + c.id + '/requirements');
            const reqs = (resp && resp.requirements) || [];
            for (const r of reqs) {
              allReqs.push({ ...r, case_title: c.title });
            }
          } catch {}
        }
        this.requirementList = allReqs;
      } catch (e) { this.showToast('加载需求关联失败: ' + e.message, 'error'); }
    },

    /* ══ 项目管理 ══ */
    async loadProjects() {
      try {
        const data = await this.apiGet('/api/projects');
        this.projectList = (data && data.projects) || [];
      } catch (e) { this.showToast('加载项目失败: ' + e.message, 'error'); }
    },
    openCreateProject() {
      this.newProject = { name: '', description: '', language: 'python', repo_url: '', path: '' };
      this.modal = { type: 'createProject', title: '新建项目' };
    },
    viewProject(p) {
      this.showToast('项目: ' + p.name + ' (环境数: ' + (p.env_count || 0) + ')', 'info');
    },
    async deleteProject(p) {
      if (!confirm('确认删除项目「' + p.name + '」？')) return;
      try {
        await this.apiDelete('/api/projects/' + p.id);
        this.showToast('项目已删除', 'success');
        this.loadProjects();
      } catch (e) { this.showToast('删除失败: ' + e.message, 'error'); }
    },


    addAssertRow() {
      if (!this.newApiCase.asserts) this.newApiCase.asserts = [];
      this.newApiCase.asserts.push({ type: 'status_code', expr: '', expected: '' });
    },
    removeAssertRow(i) {
      if (!this.newApiCase.asserts) return;
      this.newApiCase.asserts.splice(i, 1);
    },
    addVariableRow() {
      if (!this.newApiCase.variables) this.newApiCase.variables = [];
      this.newApiCase.variables.push({ name: '', type: 'jsonpath', expr: '' });
    },
    removeVariableRow(i) {
      if (!this.newApiCase.variables) return;
      this.newApiCase.variables.splice(i, 1);
    },
    addScenarioStep() {
      if (!this.newScenario.steps_arr) this.newScenario.steps_arr = [];
      this.newScenario.steps_arr.push({ type: 'case', name: '' });
    },
    removeScenarioStep(i) {
      if (!this.newScenario.steps_arr) return;
      this.newScenario.steps_arr.splice(i, 1);
    },
    closeModal() { this.modal = null; },
  },

  mounted() {
    this.connectWS();
    this.loadDashboard();
    this.loadApiMeta();
  },
});

app.mount('#app');
