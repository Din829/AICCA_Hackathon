'use client'

import { Message } from '../MessageList'
import { Skeleton } from '../../ui/skeleton'
import { formatMessageContent } from '../../../lib/utils/text'

interface AgentThinkingProps {
  message: Message
}

export default function AgentThinking({ message }: AgentThinkingProps) {
  const formattedContent = formatMessageContent(message.content)
  
  return (
    <div className="flex justify-start">
      <div className="max-w-[80%] text-muted-foreground italic">
        <p className="text-sm mb-2 whitespace-pre-wrap">{formattedContent}</p>
        <div className="space-y-2">
          <Skeleton className="h-4 w-[250px]" />
          <Skeleton className="h-4 w-[200px]" />
        </div>
      </div>
    </div>
  )
}