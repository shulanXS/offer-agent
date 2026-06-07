/** 将 SSE delta 按字符排队输出，避免同一网络包内批量更新导致“瞬间显示”。 */
export class TypewriterStream {
  private queue: string[] = []
  private running = false
  private buffer = ''
  private targetId = ''
  private readonly onUpdate: (targetId: string, content: string) => void
  private readonly charDelayMs: number

  constructor(onUpdate: (targetId: string, content: string) => void, charDelayMs = 16) {
    this.onUpdate = onUpdate
    this.charDelayMs = charDelayMs
  }

  setTarget(messageId: string) {
    this.targetId = messageId
    this.buffer = ''
    this.queue = []
    this.running = false
  }

  enqueue(text: string) {
    if (!text || !this.targetId) return
    this.queue.push(text)
    void this.pump()
  }

  async waitForIdle() {
    while (this.running || this.queue.length > 0) {
      await sleep(20)
    }
  }

  private async pump() {
    if (this.running || !this.targetId) return
    this.running = true
    try {
      while (this.queue.length > 0) {
        const piece = this.queue.shift()!
        for (const char of piece) {
          this.buffer += char
          this.onUpdate(this.targetId, this.buffer)
          await sleep(this.charDelayMs)
        }
      }
    } finally {
      this.running = false
      if (this.queue.length > 0) {
        void this.pump()
      }
    }
  }
}

function sleep(ms: number) {
  return new Promise<void>((resolve) => {
    window.setTimeout(resolve, ms)
  })
}
