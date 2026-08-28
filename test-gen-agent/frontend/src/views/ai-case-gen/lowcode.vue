<template>
  <div class="ai-lowcode">
    <a-card :bordered="false" title="✨ 低代码生成">
      <a-space direction="vertical" size="large" style="width: 100%">
        <p>用自然语言描述你的测试意图，AI 自动生成可运行的 pytest 测试用例。</p>
        <a-textarea
          v-model="description"
          :auto-size="{ minRows: 4, maxRows: 10 }"
          placeholder="例如：生成一个登录接口的测试，校验用户名密码正确时返回 token，错误时返回 401"
        />
        <a-button type="primary" :loading="generating" @click="handleLowcode">
          {{ generating ? '生成中…' : '🚀 生成用例' }}
        </a-button>
        <pre v-if="generated" class="code-block"><code>{{ generated }}</code></pre>
        <a-empty v-if="!generated && !generating" description="输入描述后点击生成" />
      </a-space>
    </a-card>
  </div>
</template>

<script setup lang="ts">
  import { ref } from 'vue';
  import { Message } from '@arco-design/web-vue';

  import { generateAiLowcode } from '@/api/modules/ai-case-gen';

  const description = ref('');
  const generating = ref(false);
  const generated = ref('');

  async function handleLowcode() {
    if (!description.value.trim()) {
      Message.error('请描述测试意图');
      return;
    }
    generating.value = true;
    generated.value = '';
    try {
      const res: any = await generateAiLowcode({ description: description.value });
      generated.value = res?.code || res?.generated_tests || JSON.stringify(res, null, 2);
      Message.success('生成成功');
    } catch (e: any) {
      Message.error(`生成失败：${e?.message || e}`);
    } finally {
      generating.value = false;
    }
  }
</script>

<style scoped>
  .ai-lowcode {
    padding: 16px;
  }
  .code-block {
    overflow: auto;
    padding: 12px;
    width: 100%;
    font-size: 13px;
    border-radius: 6px;
    white-space: pre-wrap;
    color: #abb2bf;
    background: #282c34;
    line-height: 1.6;
    word-break: break-all;
  }
</style>
