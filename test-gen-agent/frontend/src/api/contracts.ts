// frontend/src/api/contracts.ts
/**
 * 前端 API 契约统一映射表
 * =========================
 * Phase 5 重构目标：前端路径与后端路径共用一份映射，消灭适配层。
 *
 * 使用方式:
 *   import { Api } from './contracts'
 *   Api.case.page.url   // POST /functional/case/page
 *   Api.case.detail(1)  // GET /functional/case/detail/1
 */

export type HttpMethod = 'GET' | 'POST' | 'PUT' | 'DELETE' | 'PATCH'

export interface ApiEndpoint {
  method: HttpMethod
  url: string | ((...args: any[]) => string)
  description?: string
}

export interface ApiModule {
  [key: string]: ApiEndpoint
}

/**
 * 统一 API 契约定义
 *
 * 所有前端 API 调用都应通过此表引用 URL 和方法，
 * 后端路由也应与这里保持一致，减少路径不匹配。
 */
export const Api = {
  // ── 功能用例管理 ─────────────────────────────────────────
  case: {
    page: { method: 'POST', url: '/functional/case/page' },
    detail: (id: string) => ({ method: 'GET', url: `/functional/case/detail/${id}` }),
    add: { method: 'POST', url: '/functional/case/add' },
    update: { method: 'POST', url: '/functional/case/update' },
    delete: { method: 'POST', url: '/functional/case/delete' },
    batchDelete: { method: 'POST', url: '/functional/case/batch/delete' },
    batchRecover: { method: 'POST', url: '/functional/case/batch/recover' },
    trashPage: { method: 'POST', url: '/functional/case/trash/page' },
    moduleTree: { method: 'GET', url: '/functional/case/module/tree' },
    moduleCount: { method: 'GET', url: '/functional/case/module/count' },
    mindList: { method: 'GET', url: '/functional/mind/case/list' },
    reviewPage: { method: 'POST', url: '/functional/case/review/page' },
    dependencies: { method: 'POST', url: '/functional/case/dependency/page' },
    versionPage: { method: 'POST', url: '/functional/case/version/page' },
    changePage: { method: 'POST', url: '/functional/case/change/page' },
  },

  // ── 缺陷管理 ─────────────────────────────────────────────
  bug: {
    page: { method: 'POST', url: '/bug/page' },
    detail: (id: string) => ({ method: 'GET', url: `/bug/get/${id}` }),
    add: { method: 'POST', url: '/bug/add' },
    update: { method: 'POST', url: '/bug/update' },
    delete: { method: 'POST', url: '/bug/delete' },
    trashPage: { method: 'POST', url: '/bug/trash/page' },
    recover: { method: 'POST', url: '/bug/recover' },
    customField: (projectId: string) => ({ method: 'GET', url: `/bug/header/custom-field/${projectId}` }),
    columnsOption: (projectId: string) => ({ method: 'GET', url: `/bug/columns-option/${projectId}` }),
    statusFlow: { method: 'GET', url: '/bug/status-flow' },
  },

  // ── 接口定义 ─────────────────────────────────────────────
  apiDefinition: {
    page: { method: 'POST', url: '/api/definition/page' },
    moduleTree: { method: 'GET', url: '/api/definition/module/tree' },
    moduleAdd: { method: 'POST', url: '/api/definition/module/add' },
    moduleCount: { method: 'GET', url: '/api/definition/module/count' },
    trashPage: { method: 'POST', url: '/api/definition/trash/page' },
  },

  // ── 接口用例 ─────────────────────────────────────────────
  apiCase: {
    page: { method: 'POST', url: '/api/case/page' },
    moduleTree: { method: 'GET', url: '/api/case/module/tree' },
    moduleAdd: { method: 'POST', url: '/api/case/module/add' },
    moduleCount: { method: 'GET', url: '/api/case/module/count' },
  },

  // ── 场景编排 ─────────────────────────────────────────────
  scenario: {
    page: { method: 'POST', url: '/api/scenario/page' },
    moduleTree: { method: 'GET', url: '/api/scenario/module/tree' },
    moduleAdd: { method: 'POST', url: '/api/scenario/module/add' },
    moduleCount: { method: 'GET', url: '/api/scenario/module/count' },
  },

  // ── Mock 服务 ────────────────────────────────────────────
  mock: {
    page: { method: 'POST', url: '/api/mock/page' },
    moduleTree: { method: 'GET', url: '/api/mock/module/tree' },
    add: { method: 'POST', url: '/api/mock/add' },
    delete: (id: string) => ({ method: 'DELETE', url: `/api/mock/delete/${id}` }),
  },

  // ── 环境管理 ─────────────────────────────────────────────
  environment: {
    list: { method: 'GET', url: '/project/environment/list' },
    add: { method: 'POST', url: '/project/environment/add' },
    get: (id: string) => ({ method: 'GET', url: `/project/environment/get/${id}` }),
    delete: (id: string) => ({ method: 'POST', url: `/project/environment/delete/${id}` }),
  },

  // ── 调试 ─────────────────────────────────────────────────
  debug: {
    test: { method: 'POST', url: '/api/debug' },
    moduleTree: { method: 'GET', url: '/api/debug/module/tree' },
    moduleAdd: { method: 'POST', url: '/api/debug/module/add' },
    moduleCount: { method: 'GET', url: '/api/debug/module/count' },
  },

  // ── 工作台 ───────────────────────────────────────────────
  dashboard: {
    home: { method: 'GET', url: '/dashboard/home' },
  },

  // ── 测试计划 ─────────────────────────────────────────────
  testPlan: {
    page: { method: 'POST', url: '/test-plan/page' },
    detail: (id: string) => ({ method: 'GET', url: `/test-plan/detail/${id}` }),
    add: { method: 'POST', url: '/test-plan/add' },
    update: { method: 'POST', url: '/test-plan/update' },
    delete: { method: 'POST', url: '/test-plan/delete' },
  },

  // ── 报告中心 ─────────────────────────────────────────────
  report: {
    casePage: { method: 'POST', url: '/api/report/case/page' },
    scenarioPage: { method: 'POST', url: '/api/report/scenario/page' },
    shareGen: { method: 'POST', url: '/api/report/share/gen' },
    shareGet: { method: 'GET', url: '/api/report/share/get' },
  },

  // ── AI 功能 ──────────────────────────────────────────────
  ai: {
    conversation: { method: 'POST', url: '/ai/conversation' },
    chatList: (id: string) => ({ method: 'GET', url: `/ai/conversation/chat/list/${id}` }),
    configList: { method: 'GET', url: '/ai/config/list' },
  },

  // ── 系统管理 ─────────────────────────────────────────────
  system: {
    userPage: { method: 'GET', url: '/system/user/page' },
    userGet: { method: 'GET', url: '/system/user/get' },
    orgList: { method: 'GET', url: '/system/organization/list' },
    projectList: { method: 'GET', url: '/system/project/list' },
  },

  // ── 项目管理 ─────────────────────────────────────────────
  project: {
    memberAdd: { method: 'POST', url: '/project/member/add' },
    memberList: { method: 'GET', url: '/project/member/list' },
    memberRemove: { method: 'POST', url: '/project/member/remove' },
  },
} as const

export type ApiContract = typeof Api

export default Api
