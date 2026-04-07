<template>
  <div class="dashboard-container">
    <!-- 顶部统计卡片 -->
    <el-row :gutter="20" class="dashboard-header">
      <el-col :span="6">
        <el-card class="stat-card">
          <el-statistic
            title="总能耗"
            :value="12845.67"
            suffix="kWh"
          />
          <div class="stat-footer">
            <span class="trend-down">↓ 3.2%</span>
            <span class="stat-label">较昨日</span>
          </div>
        </el-card>
      </el-col>
      
      <el-col :span="6">
        <el-card class="stat-card">
          <el-statistic
            title="碳排放"
            :value="8.45"
            :precision="2"
            suffix="吨"
          />
          <div class="stat-footer">
            <span class="trend-down">↓ 12.5%</span>
            <span class="stat-label">较上月</span>
          </div>
        </el-card>
      </el-col>
      
      <el-col :span="6">
        <el-card class="stat-card">
          <el-statistic
            title="能源成本"
            :value="9876.54"
            :precision="2"
            prefix="¥"
          />
          <div class="stat-footer">
            <span class="trend-up">↑ 5.2%</span>
            <span class="stat-label">较上月</span>
          </div>
        </el-card>
      </el-col>
      
      <el-col :span="6">
        <el-card class="stat-card">
          <el-statistic
            title="设备在线率"
            :value="98.5"
            suffix="%"
          />
          <div class="stat-footer">
            <span class="status-good">正常运行</span>
          </div>
        </el-card>
      </el-col>
    </el-row>

    <!-- Grafana 仪表盘占位 -->
    <el-row :gutter="20" class="dashboard-content">
      <el-col :span="24">
        <el-card>
          <template #header>
            <div class="card-header">
              <span>能源实时监控</span>
              <el-button text type="primary">
                <el-icon><Refresh /></el-icon>
                刷新
              </el-button>
            </div>
          </template>
          
          <div class="grafana-placeholder">
            <el-empty description="Grafana 仪表盘将在此处显示">
              <el-button type="primary">配置 Grafana 连接</el-button>
            </el-empty>
          </div>
        </el-card>
      </el-col>
    </el-row>

    <!-- 数据表格 -->
    <el-row :gutter="20" class="dashboard-table">
      <el-col :span="24">
        <el-card>
          <template #header>
            <span>子站实时数据</span>
          </template>
          
          <el-table :data="tableData" style="width: 100%">
            <el-table-column prop="station" label="子站名称" width="180" />
            <el-table-column prop="power" label="实时功率 (kW)" width="150">
              <template #default="{ row }">
                <el-tag :type="row.power > 1000 ? 'danger' : 'success'">
                  {{ row.power }}
                </el-tag>
              </template>
            </el-table-column>
            <el-table-column prop="energy" label="今日能耗 (kWh)" width="150" />
            <el-table-column prop="status" label="运行状态" width="120">
              <template #default="{ row }">
                <el-tag :type="row.status === '正常' ? 'success' : 'warning'">
                  {{ row.status }}
                </el-tag>
              </template>
            </el-table-column>
            <el-table-column prop="updateTime" label="更新时间" />
          </el-table>
        </el-card>
      </el-col>
    </el-row>
  </div>
</template>

<script setup lang="ts">
import { ref } from 'vue'
import { Refresh } from '@element-plus/icons-vue'

// 模拟数据
const tableData = ref([
  {
    station: '子站A - 1号厂房',
    power: 856.5,
    energy: 12580.6,
    status: '正常',
    updateTime: '2024-01-03 14:30:25'
  },
  {
    station: '子站B - 2号厂房',
    power: 1235.8,
    energy: 18960.3,
    status: '正常',
    updateTime: '2024-01-03 14:30:25'
  },
  {
    station: '子站C - 办公楼',
    power: 425.3,
    energy: 6840.2,
    status: '正常',
    updateTime: '2024-01-03 14:30:25'
  },
  {
    station: '子站D - 仓库',
    power: 125.6,
    energy: 1860.5,
    status: '维护',
    updateTime: '2024-01-03 14:30:25'
  }
])
</script>

<style lang="scss" scoped>
.dashboard-container {
  padding: 20px;
  background-color: #f5f7fa;
  min-height: calc(100vh - 60px);
}

.dashboard-header {
  margin-bottom: 20px;
}

.stat-card {
  height: 100%;
  
  :deep(.el-statistic) {
    text-align: center;
  }
  
  .stat-footer {
    margin-top: 10px;
    text-align: center;
    font-size: 12px;
    
    .trend-up {
      color: #f56c6c;
    }
    
    .trend-down {
      color: #67c23a;
    }
    
    .status-good {
      color: #67c23a;
    }
    
    .stat-label {
      margin-left: 5px;
      color: #909399;
    }
  }
}

.dashboard-content,
.dashboard-table {
  margin-bottom: 20px;
}

.card-header {
  display: flex;
  justify-content: space-between;
  align-items: center;
}

.grafana-placeholder {
  height: 400px;
  display: flex;
  align-items: center;
  justify-content: center;
  background-color: #fafafa;
  border: 1px dashed #e4e7ed;
  border-radius: 4px;
}
</style>