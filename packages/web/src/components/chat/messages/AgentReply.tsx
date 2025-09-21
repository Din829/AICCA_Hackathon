'use client'

import { Message } from '../MessageList'
import { formatMessageContent } from '../../../lib/utils/text'

interface AgentReplyProps {
  message: Message
}

export default function AgentReply({ message }: AgentReplyProps) {
  const { riskScore } = message.metadata || {}
  const formattedContent = formatMessageContent(message.content)

  return (
    <div className="flex justify-start">
      <div className="max-w-[80%] rounded-lg bg-muted px-4 py-2">
        <div className="text-sm whitespace-pre-wrap">{formattedContent}</div>
        
        {riskScore !== undefined && (
          <div className="mt-2 pt-2 border-t">
            <span className="text-xs text-muted-foreground">
              リスクスコア: {' '}
              <span className={`font-medium ${
                riskScore < 30 ? 'text-green-600' :
                riskScore < 70 ? 'text-yellow-600' :
                'text-red-600'
              }`}>
                {riskScore}/100
              </span>
            </span>
          </div>
        )}
      </div>
    </div>
  )
}