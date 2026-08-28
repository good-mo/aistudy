import MSR from '@/api/http/index';
import {
  AiGenerateStructuredUrl,
  AiGenerateUrl,
  AiLowcodeUrl,
  AiProjectGenerateUrl,
  AiProjectScanUrl,
  AiRunTaskUrl,
  AiSkillPathUrl,
  AiTestTypesUrl,
} from '@/api/requrls/ai-case-gen';

// 测试类型
export interface TestTypeInfo {
  key: string;
  label: string;
  icon: string;
  description: string;
}

// 生成请求参数
export interface AiGenerateParams {
  source_code: string;
  file_path?: string;
  test_type?: string;
  generate_script?: boolean;
  async_mode?: boolean;
}

// 结构化用例
export interface StructuredStep {
  step: string;
  data?: string;
  expected: string;
}

export interface StructuredCase {
  title: string;
  preconditions: string;
  steps: StructuredStep[];
  test_data?: string;
  priority?: string;
  risk_level?: string;
  execution_type?: string;
}

// 获取支持的测试类型
export function getAiTestTypes() {
  return MSR.get<{ types: TestTypeInfo[] }>({ url: AiTestTypesUrl });
}

// 生成测试用例
export function generateAiTests(data: AiGenerateParams) {
  return MSR.post({ url: AiGenerateUrl, data });
}

// 仅生成结构化用例
export function generateAiStructured(data: AiGenerateParams) {
  return MSR.post({ url: AiGenerateStructuredUrl, data });
}

// 扫描项目目录
export function scanAiProject(data: { project_path: string }) {
  return MSR.post({ url: AiProjectScanUrl, data });
}

// 项目批量生成
export function generateAiProject(data: { project_path: string; async_mode?: boolean }) {
  return MSR.post({ url: AiProjectGenerateUrl, data });
}

// 低代码生成
export function generateAiLowcode(data: { description: string }) {
  return MSR.post({ url: AiLowcodeUrl, data });
}

// 职业发展路径
export function getAiSkillPath() {
  return MSR.get({ url: AiSkillPathUrl });
}

// 查询异步任务结果
export function getAiTask(taskId: string) {
  return MSR.get({ url: `${AiRunTaskUrl}/${taskId}` });
}
