import { AiCaseGenRouteEnum } from '@/enums/routeEnum';

import { DEFAULT_LAYOUT } from '../base';
import type { AppRouteRecordRaw } from '../types';

const AiCaseGen: AppRouteRecordRaw = {
  path: '/ai-case-gen',
  name: AiCaseGenRouteEnum.AI_CASE_GEN,
  redirect: '/ai-case-gen/index',
  component: DEFAULT_LAYOUT,
  meta: {
    locale: 'menu.aiCaseGen',
    collapsedLocale: 'menu.aiCaseGen',
    icon: 'icon-icon_bot1',
    order: 1,
    hideChildrenInMenu: true,
    roles: ['*'],
  },
  children: [
    // AI 用例生成
    {
      path: 'index',
      name: AiCaseGenRouteEnum.AI_CASE_GEN_INDEX,
      component: () => import('@/views/ai-case-gen/index.vue'),
      meta: {
        locale: 'menu.aiCaseGenIndex',
        roles: ['*'],
        isTopMenu: true,
      },
    },
    // 低代码生成
    {
      path: 'lowcode',
      name: AiCaseGenRouteEnum.AI_CASE_GEN_LOWCODE,
      component: () => import('@/views/ai-case-gen/lowcode.vue'),
      meta: {
        locale: 'menu.aiCaseGenLowcode',
        roles: ['*'],
        isTopMenu: true,
      },
    },
    // 项目批量生成
    {
      path: 'project',
      name: AiCaseGenRouteEnum.AI_CASE_GEN_PROJECT,
      component: () => import('@/views/ai-case-gen/project.vue'),
      meta: {
        locale: 'menu.aiCaseGenProject',
        roles: ['*'],
        isTopMenu: true,
      },
    },
  ],
};

export default AiCaseGen;
