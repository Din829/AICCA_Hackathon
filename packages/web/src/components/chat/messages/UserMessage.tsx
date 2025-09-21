'use client'

import { Message } from '../MessageList'
import { formatMessageContent } from '../../../lib/utils/text'

interface UserMessageProps {
  message: Message
}

export default function UserMessage({ message }: UserMessageProps) {
  const formattedContent = formatMessageContent(message.content)
  
  return (
    <div className="flex justify-end">
      <div className="max-w-[80%] rounded-lg bg-primary text-primary-foreground px-4 py-2">
        <p className="text-sm whitespace-pre-wrap">{formattedContent}</p>
      </div>
    </div>
  )
}