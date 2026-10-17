// R7：登录对话框状态机 hook。
import { useState } from 'react'
import type { AuthMode } from '../components/AuthPage'

export function useAuthDialog() {
  const [isOpen, setIsOpen] = useState(false)
  const [mode, setMode] = useState<AuthMode>('login')
  const [username, setUsername] = useState('')
  const [password, setPassword] = useState('')
  const [error, setError] = useState('')
  const [notice, setNotice] = useState('')
  const [isSubmitting, setIsSubmitting] = useState(false)

  function open(mode: AuthMode = 'login') {
    setMode(mode)
    setError('')
    setNotice('')
    setIsOpen(true)
  }

  function close() {
    setIsOpen(false)
    setError('')
    setNotice('')
  }

  function reset() {
    setUsername('')
    setPassword('')
  }

  return {
    isOpen,
    mode,
    username,
    password,
    error,
    notice,
    isSubmitting,
    setMode,
    setUsername,
    setPassword,
    setError,
    setNotice,
    setIsSubmitting,
    open,
    close,
    reset,
  }
}
