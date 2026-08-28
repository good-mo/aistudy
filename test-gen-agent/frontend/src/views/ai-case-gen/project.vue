<template>
  <div class="ai-project">
    <a-card :bordered="false" title="📁 项目批量生成">
      <a-space direction="vertical" size="large" style="width: 100%">
        <p>指定项目目录，自动扫描所有源文件并批量生成测试用例。</p>
        <a-input v-model="projectPath" placeholder="项目目录路径（如 /path/to/project）" />
        <a-space>
          <a-button @click="handleScan">🔍 扫描项目</a-button>
          <a-button type="primary" :loading="generating" @click="handleBatchGenerate">
            {{ generating ? '生成中…' : '🚀 批量生成' }}
          </a-button>
        </a-space>

        <!-- 扫描结果 -->
        <a-table
          v-if="scannedFiles.length"
          :data="scannedFiles"
          :pagination="{ pageSize: 10 }"
          row-key="path"
          style="margin-top: 8px"
        >
          <template #columns>
            <a-table-column title="文件" data-index="relative_path" />
            <a-table-column title="大小(B)" data-index="size" :width="100" />
            <a-table-column title="函数数" data-index="signatures" :width="100">
              <template #cell="{ record }">
                {{ record.signatures?.length ?? 0 }}
              </template>
            </a-table-column>
          </template>
        </a-table>
        <a-empty v-if="!scannedFiles.length" description="扫描后展示项目文件" />

        <!-- 批量生成结果汇总 -->
        <a-result v-if="batchResult?.total" status="success" :title="`共生成 ${batchResult.total} 个文件`">
          <template #subtitle>
            <a-table :data="batchResult.results" :pagination="{ pageSize: 10 }" size="small" style="margin-top: 8px">
              <template #columns>
                <a-table-column title="文件" data-index="file_path" />
                <a-table-column title="结果" :width="120">
                  <template #cell="{ record }">
                    {{ record.test_result?.passed ? '✅ 通过' : '❌ 失败' }}
                  </template>
                </a-table-column>
              </template>
            </a-table>
          </template>
        </a-result>
      </a-space>
    </a-card>
  </div>
</template>

<script setup lang="ts">
  import { ref } from 'vue';
  import { Message } from '@arco-design/web-vue';

  import { generateAiProject, scanAiProject } from '@/api/modules/ai-case-gen';

  const projectPath = ref('');
  const scannedFiles = ref<any[]>([]);
  const generating = ref(false);
  const batchResult = ref<any>(null);

  async function handleScan() {
    if (!projectPath.value.trim()) {
      Message.error('请输入项目目录路径');
      return;
    }
    try {
      const res: any = await scanAiProject({ project_path: projectPath.value });
      scannedFiles.value = res?.files || [];
      Message.success(`扫描到 ${scannedFiles.value.length} 个文件`);
    } catch (e: any) {
      Message.error(`扫描失败：${e?.message || e}`);
    }
  }

  async function handleBatchGenerate() {
    if (!projectPath.value.trim()) {
      Message.error('请输入项目目录路径');
      return;
    }
    generating.value = true;
    batchResult.value = null;
    try {
      const res: any = await generateAiProject({ project_path: projectPath.value });
      batchResult.value = res;
      Message.success(`批量生成完成，共 ${res?.total ?? 0} 个文件`);
    } catch (e: any) {
      Message.error(`批量生成失败：${e?.message || e}`);
    } finally {
      generating.value = false;
    }
  }
</script>

<style scoped>
  .ai-project {
    padding: 16px;
  }
</style>
