import { ref, onUnmounted } from 'vue'
import { io, Socket } from 'socket.io-client'

export const useWebSocket = () => {
  const socket = ref<Socket | null>(null)
  const connected = ref(false)

  const connect = (url?: string) => {
    const wsUrl = url || import.meta.env.VITE_WS_URL || 'ws://localhost:3000'
    
    socket.value = io(wsUrl, {
      transports: ['websocket'],
      autoConnect: true
    })

    socket.value.on('connect', () => {
      connected.value = true
      console.log('WebSocket connected')
    })

    socket.value.on('disconnect', () => {
      connected.value = false
      console.log('WebSocket disconnected')
    })
  }

  const disconnect = () => {
    if (socket.value) {
      socket.value.disconnect()
      socket.value = null
    }
  }

  const subscribe = (event: string, callback: (data: any) => void) => {
    if (socket.value) {
      socket.value.on(event, callback)
    }
  }

  const unsubscribe = (event: string) => {
    if (socket.value) {
      socket.value.off(event)
    }
  }

  const emit = (event: string, data: any) => {
    if (socket.value && connected.value) {
      socket.value.emit(event, data)
    }
  }

  onUnmounted(() => {
    disconnect()
  })

  return {
    socket,
    connected,
    connect,
    disconnect,
    subscribe,
    unsubscribe,
    emit
  }
}