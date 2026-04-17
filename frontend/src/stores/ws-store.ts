import { create } from 'zustand'

interface WsState {
  status: 'connecting' | 'connected' | 'disconnected'
  setStatus: (status: 'connecting' | 'connected' | 'disconnected') => void
}

export const useWsStore = create<WsState>((set) => ({
  status: 'disconnected',
  setStatus: (status) => set({ status }),
}))
