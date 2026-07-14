"""
WebSocket Client Helper - For Frontend Integration
===================================================
JavaScript/React helper to connect frontend UI to FastAPI backend

Usage in React:
```jsx
import { EchoSignClient } from './echosign-client'

const client = new EchoSignClient('ws://localhost:8000')
await client.connect()
await client.sendFrame(canvasImage)
const prediction = await client.getResult()
```
"""

// echosign-client.js
export class EchoSignClient {
  constructor(wsUrl = 'ws://localhost:8000') {
    this.wsUrl = `${wsUrl}/ws/live`
    this.ws = null
    this.messageHandlers = {}
    this.requestId = 0
  }

  /**
   * Connect to backend WebSocket
   */
  async connect() {
    return new Promise((resolve, reject) => {
      try {
        this.ws = new WebSocket(this.wsUrl)

        this.ws.onopen = () => {
          console.log('[EchoSign] WebSocket connected')
          resolve()
        }

        this.ws.onmessage = (event) => {
          try {
            const data = JSON.parse(event.data)
            console.log('[EchoSign] Received:', data)

            // Call any registered handlers
            if (data.type && this.messageHandlers[data.type]) {
              this.messageHandlers[data.type](data)
            }
          } catch (e) {
            console.error('[EchoSign] Parse error:', e)
          }
        }

        this.ws.onerror = (error) => {
          console.error('[EchoSign] WebSocket error:', error)
          reject(error)
        }

        this.ws.onclose = () => {
          console.log('[EchoSign] WebSocket closed')
        }
      } catch (e) {
        reject(e)
      }
    })
  }

  /**
   * Send frame for inference
   * @param {Canvas|ImageData|Blob} frameData - Image data
   */
  async sendFrame(frameData) {
    if (!this.ws || this.ws.readyState !== WebSocket.OPEN) {
      throw new Error('WebSocket not connected')
    }

    return new Promise((resolve) => {
      // Register handler for response
      const handler = (data) => {
        if (data.type === 'inference_result') {
          resolve(data)
          delete this.messageHandlers['inference_result']
        }
      }

      this.messageHandlers['inference_result'] = handler

      // Convert canvas to base64
      let base64Data

      if (frameData instanceof HTMLCanvasElement) {
        base64Data = frameData.toDataURL('image/jpeg').split(',')[1]
      } else if (frameData instanceof Blob) {
        const reader = new FileReader()
        reader.onload = () => {
          base64Data = reader.result.split(',')[1]
          this.ws.send(base64Data)
        }
        reader.readAsDataURL(frameData)
        return
      } else {
        throw new Error('Unsupported frame format')
      }

      this.ws.send(base64Data)
    })
  }

  /**
   * Keep connection alive
   */
  startHeartbeat(interval = 30000) {
    this.heartbeatInterval = setInterval(() => {
      if (this.ws && this.ws.readyState === WebSocket.OPEN) {
        this.ws.send('ping')
      }
    }, interval)
  }

  stopHeartbeat() {
    if (this.heartbeatInterval) {
      clearInterval(this.heartbeatInterval)
    }
  }

  /**
   * Close connection
   */
  disconnect() {
    this.stopHeartbeat()
    if (this.ws) {
      this.ws.close()
    }
  }

  /**
   * Register event handler
   */
  on(eventType, handler) {
    this.messageHandlers[eventType] = handler
  }

  /**
   * Unregister event handler
   */
  off(eventType) {
    delete this.messageHandlers[eventType]
  }
}

// React Hook Example
export function useEchoSign() {
  const [client, setClient] = React.useState(null)
  const [connected, setConnected] = React.useState(false)

  React.useEffect(() => {
    const echoClient = new EchoSignClient()

    echoClient.connect()
      .then(() => {
        setClient(echoClient)
        setConnected(true)
        echoClient.startHeartbeat()
      })
      .catch(err => console.error('Connection failed:', err))

    return () => {
      echoClient.disconnect()
    }
  }, [])

  return { client, connected }
}
