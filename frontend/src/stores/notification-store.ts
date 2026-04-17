import { create } from 'zustand'

interface Notification {
  id: string
  type: 'info' | 'success' | 'warning' | 'error'
  message: string
}

interface NotificationState {
  notifications: Notification[]
  addNotification: (type: Notification['type'], message: string) => void
  removeNotification: (id: string) => void
}

let nextId = 0

export const useNotificationStore = create<NotificationState>((set) => ({
  notifications: [],
  addNotification: (type, message) => {
    const id = String(++nextId)
    set((state) => ({
      notifications: [...state.notifications, { id, type, message }],
    }))
    setTimeout(() => {
      set((state) => ({
        notifications: state.notifications.filter((n) => n.id !== id),
      }))
    }, 5000)
  },
  removeNotification: (id) =>
    set((state) => ({
      notifications: state.notifications.filter((n) => n.id !== id),
    })),
}))
