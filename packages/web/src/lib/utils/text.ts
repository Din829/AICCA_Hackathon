/**
 * 清理Markdown格式符号的工具函数
 */

/**
 * 简单清理Markdown格式
 * 移除常见的Markdown符号但保留内容
 */
export function cleanMarkdown(text: string): string {
  if (!text) return ''
  
  return text
    // 移除加粗符号 **text** 或 __text__
    .replace(/\*\*([^*]+)\*\*/g, '$1')
    .replace(/__([^_]+)__/g, '$1')
    // 移除斜体符号 *text* 或 _text_
    .replace(/\*([^*]+)\*/g, '$1')
    .replace(/_([^_]+)_/g, '$1')
    // 移除行内代码符号 `code`
    .replace(/`([^`]+)`/g, '$1')
    // 移除标题符号 # ## ###
    .replace(/^#{1,6}\s+/gm, '')
    // 移除链接但保留文本 [text](url)
    .replace(/\[([^\]]+)\]\([^)]+\)/g, '$1')
    // 移除列表符号 - * +
    .replace(/^[\-\*\+]\s+/gm, '• ')
    // 移除引用符号 >
    .replace(/^>\s+/gm, '')
    // 清理多余的空行
    .replace(/\n{3,}/g, '\n\n')
    .trim()
}

/**
 * 格式化为显示友好的文本
 * 保留基本的段落结构
 */
export function formatMessageContent(text: string): string {
  const cleaned = cleanMarkdown(text)
  
  // 将换行转换为段落
  const paragraphs = cleaned.split('\n\n').filter(p => p.trim())
  
  return paragraphs.join('\n\n')
}

/**
 * 将文本转换为HTML安全的格式
 * 处理换行和基本格式
 */
export function textToSafeHtml(text: string): string {
  const cleaned = cleanMarkdown(text)
  
  // 转义HTML特殊字符
  const escaped = cleaned
    .replace(/&/g, '&amp;')
    .replace(/</g, '&lt;')
    .replace(/>/g, '&gt;')
    .replace(/"/g, '&quot;')
    .replace(/'/g, '&#039;')
  
  // 将换行转换为<br>标签
  return escaped.replace(/\n/g, '<br>')
}