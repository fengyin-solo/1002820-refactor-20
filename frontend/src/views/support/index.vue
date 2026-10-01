<template>
  <section class="page" data-module="support">
    <header class="page-head">
      <div>
        <h2>树木支撑管理</h2>
        <p class="page-desc">维护支撑设施，围绕支撑编号、所属树木、支撑方式、支撑材料做登记、筛选与状态流转。</p>
      </div>
      <div class="page-actions">
        <button class="btn primary" type="button" @click="openCreate">登记支撑设施</button>
        <button class="btn" type="button" @click="exportRows">导出树木支撑清单</button>
      </div>
    </header>

    <div class="stat-row">
      <article v-for="item in stats" :key="item.label" class="stat-card">
        <span class="stat-label">{{ item.label }}</span>
        <strong class="stat-value">{{ item.value }}</strong>
      </article>
    </div>

    <form class="filter-bar" @submit.prevent="reload">
      <label v-for="field in filterFields" :key="field" class="filter-item">
        <span>{{ field }}</span>
        <input v-model="filters[field]" :placeholder="`按${field}检索`" />
      </label>
      <button class="btn" type="submit">查询</button>
      <button class="btn ghost" type="button" @click="resetFilters">重置条件</button>
    </form>

    <table class="data-table">
      <thead>
        <tr>
          <th v-for="column in columns" :key="column">{{ column }}</th>
          <th>可执行动作</th>
        </tr>
      </thead>
      <tbody>
        <tr v-for="row in rows" :key="String(row.id)">
          <td v-for="column in columns" :key="column">{{ row[column] ?? '—' }}</td>
          <td class="row-actions">
            <button
              v-for="action in actions"
              :key="action"
              class="link"
              type="button"
              @click="runAction(action, row)"
            >
              {{ action }}
            </button>
          </td>
        </tr>
        <tr v-if="!rows.length">
          <td :colspan="columns.length + 1" class="empty-state">暂无树木支撑数据，可先登记支撑设施</td>
        </tr>
      </tbody>
    </table>

    <footer class="page-foot">
      <span>共 {{ total }} 条树木支撑记录</span>
      <span v-if="errorMessage" class="error-text">{{ errorMessage }}</span>
    </footer>
  </section>
</template>

<script setup lang="ts">
import { onMounted, ref } from 'vue'

import { request } from '@/api/client'

type Row = Record<string, string | number | null>

const ENDPOINT = '/api/support'
const columns = ["支撑编号", "所属树木", "支撑方式", "支撑材料", "安装日期", "检查日期", "稳固情况", "支撑状态"]
const actions = ["登记松动", "加固处理", "拆除支撑"]
const statuses = ["稳固", "松动", "损坏", "已拆除"]
const stats = ref([{ label: "稳固支撑", value: 0 }, { label: "松动支撑", value: 0 }, { label: "损坏支撑", value: 0 }])

const rows = ref<Row[]>([])
const total = ref(0)
const errorMessage = ref('')
const filters = ref<Record<string, string>>({})
const filterFields = columns.slice(0, 3)

function resetFilters() {
  filters.value = {}
  void reload()
}

function exportRows() {
  window.open(`${ENDPOINT}/export`, '_blank')
}

function openCreate() {
  errorMessage.value = '支撑设施登记入口尚未接入审批流'
}

async function runAction(action: string, row: Row) {
  errorMessage.value = ''
  try {
    const response = await request(`${ENDPOINT}/${row.id}/actions`, {
      method: 'POST',
      body: JSON.stringify({ action }),
    })
    if (!response.ok) {
      throw new Error('树木支撑动作未生效，请稍后重试')
    }
    await reload()
  } catch (error) {
    errorMessage.value = error instanceof Error ? error.message : '树木支撑操作失败'
  }
}

function refreshStats() {
  // 支撑状态统计随明细重算，不再写死
  const counts: Record<string, number> = { 稳固: 0, 松动: 0, 损坏: 0 }
  for (const row of rows.value) {
    const status = String(row['支撑状态'] ?? '')
    if (status in counts) counts[status] += 1
  }
  stats.value = [
    { label: '稳固支撑', value: counts['稳固'] },
    { label: '松动支撑', value: counts['松动'] },
    { label: '损坏支撑', value: counts['损坏'] },
  ]
}

async function reload() {
  errorMessage.value = ''
  const query = new URLSearchParams(filters.value as Record<string, string>).toString()
  try {
    const response = await request(`${ENDPOINT}?${query}`)
    if (!response.ok) {
      throw new Error('支撑设施列表读取失败')
    }
    const payload = await response.json()
    rows.value = payload.items ?? []
    total.value = payload.total ?? rows.value.length
    refreshStats()
  } catch (error) {
    errorMessage.value = error instanceof Error ? error.message : '树木支撑列表读取失败'
  }
}

onMounted(reload)
</script>
