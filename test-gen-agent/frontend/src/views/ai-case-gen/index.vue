<template>
  <div class="ai-case-gen">
    <a-space direction="vertical" size="large" style="width: 100%">
      <!-- 页面标题 -->
      <div class="page-header">
        <h2 class="page-title">🧪 AI 用例生成</h2>
        <p class="page-desc">输入源码，AI 自动生成结构化测试用例与可执行 pytest 脚本</p>
      </div>

      <!-- 测试类型选择 -->
      <a-card title="① 选择测试类型" :bordered="false" class="section-card">
        <a-row :gutter="[16, 16]">
          <a-col v-for="t in testTypes" :key="t.key" :xs="12" :sm="8" :md="6" :lg="4">
            <div class="test-type-card" :class="{ active: currentType === t.key }" @click="currentType = t.key">
              <div class="type-icon">{{ t.icon }}</div>
              <div class="type-name">{{ t.label }}</div>
              <div class="type-desc">{{ t.description }}</div>
            </div>
          </a-col>
        </a-row>
      </a-card>

      <!-- 源码输入 -->
      <a-card title="② 输入源码" :bordered="false" class="section-card">
        <a-space direction="vertical" size="small" style="width: 100%">
          <a-input v-model="form.filePath" placeholder="文件名（如 demo.py）" style="width: 300px" />
          <a-textarea
            v-model="form.sourceCode"
            :auto-size="{ minRows: 8, maxRows: 20 }"
            placeholder="粘贴待测试的源代码……"
          />
          <a-space>
            <a-button type="primary" :loading="generating" @click="handleGenerate">
              {{ generating ? '生成中…' : '🚀 生成测试用例' }}
            </a-button>
            <a-button :loading="generating" @click="handleGenerateStructured"> 生成结构化用例 </a-button>
            <a-switch v-model="form.generateScript" />
            <span>同时生成脚本</span>
          </a-space>
        </a-space>
      </a-card>

      <!-- 生成结果 -->
      <a-card v-if="result || structuredCases.length" title="③ 生成结果" :bordered="false" class="section-card">
        <a-tabs>
          <!-- 结构化用例视图 -->
          <a-tab-pane key="structured" title="📋 结构化用例">
            <div v-for="(c, i) in structuredCases" :key="i" class="struct-case">
              <h4>{{ i + 1 }}. {{ c.title }}</h4>
              <p><b>前置条件：</b>{{ c.preconditions || '-' }}</p>
              <p v-if="c.priority"><b>优先级：</b>{{ c.priority }}</p>
              <a-table :data="c.steps" :pagination="false" size="small" :bordered="true" style="margin-top: 8px">
                <template #columns>
                  <a-table-column title="步骤" data-index="step" />
                  <a-table-column title="输入数据" data-index="data" />
                  <a-table-column title="预期结果" data-index="expected" />
                </template>
              </a-table>
            </div>
            <a-empty v-if="!structuredCases.length" description="无结构化用例数据" />
          </a-tab-pane>

          <!-- 代码视图 -->
          <a-tab-pane key="code" title="💻 测试代码">
            <pre class="code-block"><code>{{ result?.generated_tests || '暂无代码' }}</code></pre>
          </a-tab-pane>
        </a-tabs>

        <!-- 执行结果摘要 -->
        <a-descriptions
          v-if="result?.test_result"
          title="测试执行结果"
          :column="3"
          bordered
          size="small"
          style="margin-top: 16px"
        >
          <a-descriptions-item label="通过">
            {{ result.test_result.passed ? '✅' : '❌' }}
          </a-descriptions-item>
          <a-descriptions-item label="通过数">{{ result.test_result.passed_count }}</a-descriptions-item>
          <a-descriptions-item label="失败数">{{ result.test_result.failed_count }}</a-descriptions-item>
          <a-descriptions-item label="覆盖率">
            {{ result.coverage_report?.coverage_pct ?? '-' }}
          </a-descriptions-item>
          <a-descriptions-item label="重试次数">{{ result.retry_count }}</a-descriptions-item>
          <a-descriptions-item label="保存路径">{{ result.saved_to || '-' }}</a-descriptions-item>
        </a-descriptions>
      </a-card>
    </a-space>
  </div>
</template>

<script setup lang="ts">
  import { onMounted, ref } from 'vue';
  import { Message } from '@arco-design/web-vue';

  import {
    generateAiStructured,
    generateAiTests,
    getAiTestTypes,
    type StructuredCase,
    type TestTypeInfo,
  } from '@/api/modules/ai-case-gen';

  const testTypes = ref<TestTypeInfo[]>([]);
  const currentType = ref('functional');
  const generating = ref(false);

  const form = ref({
    sourceCode: '',
    filePath: 'demo.py',
    generateScript: true,
  });

  const result = ref<any>(null);
  const structuredCases = ref<StructuredCase[]>([]);

  onMounted(async () => {
    try {
      const res: any = await getAiTestTypes();
      testTypes.value = res?.types || [];
      if (!testTypes.value.length) {
        testTypes.value = [
          { key: 'functional', label: '功能测试', icon: '🧪', description: '业务功能正确性' },
          { key: 'api', label: '接口测试', icon: '🔌', description: 'API 请求响应契约' },
          { key: 'ui', label: 'UI 测试', icon: '🎨', description: '用户界面交互' },
          { key: 'performance', label: '性能测试', icon: '⚡', description: '性能指标与 SLO' },
          { key: 'security', label: '安全测试', icon: '🔒', description: '安全防护' },
          { key: 'compatibility', label: '兼容性测试', icon: '🖥️', description: '跨环境兼容' },
          { key: 'reliability', label: '可靠性测试', icon: '🔧', description: '容错与稳定性' },
        ];
      }
    } catch (e) {
      Message.warning('获取测试类型失败，使用默认类型');
    }
  });

  async function handleGenerate() {
    if (!form.value.sourceCode.trim()) {
      Message.error('请先输入源码');
      return;
    }
    generating.value = true;
    try {
      const res: any = await generateAiTests({
        source_code: form.value.sourceCode,
        file_path: form.value.filePath || 'demo.py',
        test_type: currentType.value,
        generate_script: form.value.generateScript,
      });
      result.value = res;
      structuredCases.value = res?.structured_cases || [];
      if (res?.test_result?.passed) {
        Message.success('测试用例生成成功并通过');
      } else {
        Message.warning('已生成，测试执行结果请查看详情');
      }
    } catch (e: any) {
      Message.error(`生成失败：${e?.message || e}`);
    } finally {
      generating.value = false;
    }
  }

  async function handleGenerateStructured() {
    if (!form.value.sourceCode.trim()) {
      Message.error('请先输入源码');
      return;
    }
    generating.value = true;
    try {
      const res: any = await generateAiStructured({
        source_code: form.value.sourceCode,
        file_path: form.value.filePath || 'demo.py',
        test_type: currentType.value,
      });
      structuredCases.value = res?.structured_cases || [];
      result.value = null;
      Message.success(`已生成 ${structuredCases.value.length} 条结构化用例`);
    } catch (e: any) {
      Message.error(`生成失败：${e?.message || e}`);
    } finally {
      generating.value = false;
    }
  }
</script>

<style scoped lang="less">
  .ai-case-gen {
    padding: 16px;
  }
  .page-header {
    .page-title {
      margin: 0;
      font-size: 20px;
      font-weight: 600;
    }
    .page-desc {
      margin: 8px 0 0;
      color: var(--color-text-3);
    }
  }
  .section-card {
    margin-bottom: 8px;
  }
  .test-type-card {
    padding: 12px;
    border: 1px solid var(--color-border-2);
    border-radius: 6px;
    cursor: pointer;
    text-align: center;
    transition: all 0.2s;
    &:hover {
      border-color: rgb(var(--primary-6));
    }
    &.active {
      border-color: rgb(var(--primary-6));
      background: rgb(var(--primary-1));
      box-shadow: 0 2px 8px rgb(var(--primary-6) 0.2);
    }
    .type-icon {
      font-size: 28px;
    }
    .type-name {
      margin-top: 6px;
      font-weight: 500;
    }
    .type-desc {
      margin-top: 4px;
      font-size: 12px;
      color: var(--color-text-3);
    }
  }
  .struct-case {
    margin-bottom: 16px;
    padding: 12px;
    border-radius: 6px;
    background: var(--color-fill-2);
  }
  .code-block {
    overflow: auto;
    padding: 12px;
    font-size: 13px;
    border-radius: 6px;
    white-space: pre-wrap;
    color: #abb2bf;
    background: #282c34;
    line-height: 1.6;
    word-break: break-all;
  }
</style>
