'use client'

import {
  ResizablePanelGroup,
  ResizablePanel,
  ResizableHandle,
} from '../ui/resizable'
import ContentPreview from './ContentPreview'
import AnalysisResults from './AnalysisResults'

export default function ContentPanel() {
  return (
    <ResizablePanelGroup direction="vertical" className="h-full">
      {/* 上层 - 内容预览（50%） */}
      <ResizablePanel defaultSize={50} minSize={30}>
        <ContentPreview />
      </ResizablePanel>

      {/* 可拖动分隔线 */}
      <ResizableHandle />

      {/* 下层 - 检测结果（50%） */}
      <ResizablePanel defaultSize={50} minSize={30}>
        <AnalysisResults />
      </ResizablePanel>
    </ResizablePanelGroup>
  )
}