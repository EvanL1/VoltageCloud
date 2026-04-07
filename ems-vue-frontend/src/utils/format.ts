import dayjs from 'dayjs'
import 'dayjs/locale/zh-cn'

dayjs.locale('zh-cn')

export const formatTime = (time: Date | string | number) => {
  return dayjs(time).format('YYYY-MM-DD HH:mm:ss')
}

export const formatDate = (date: Date | string | number) => {
  return dayjs(date).format('YYYY-MM-DD')
}

export const formatNumber = (num: number, precision = 2) => {
  return num.toFixed(precision)
}

export const formatCurrency = (amount: number) => {
  return new Intl.NumberFormat('zh-CN', {
    style: 'currency',
    currency: 'CNY'
  }).format(amount)
}

export const formatPercent = (value: number) => {
  return `${(value * 100).toFixed(1)}%`
}