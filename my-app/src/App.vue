<template>
  <div class="panel">
    <div class="panel-header">💬 AI 助手</div>
    <div class="panel-content">
      <div class="llm-message" v-for="(message, index) in chatHistory" :key="index">
        <div class="message-status">{{ message.status || '✅ 已生成回复' }}</div>
        <div class="message-content" v-html="renderMarkdown(message.summary || message.content || message)"></div>
      </div>
      <div class="llm-message" v-if="chatHistory.length === 0">
        <div class="message-status">… 等待中</div>
        <div class="message-content">Kimi 的回复将显示在这里…</div>
      </div>
    </div>
  </div>

  <div class="resize-handle"></div>

  <div class="panel">
    <div class="panel-header">📄 论文阅读</div>
    <div class="panel-content pdf-viewer" ref="centerEl" @dragover.prevent @drop.prevent="handleFileDrop">
      <div v-if="!pdfLoaded" class="drop-zone">
        <p>将 PDF 文件拖放到此处，或</p>
        <button @click="openFileDialog" class="upload-button">选择文件</button>
        <input type="file" ref="fileInput" @change="handleFileSelect" accept=".pdf" hidden>
      </div>
      <div v-else class="pdf-page-container">
        <canvas 
          v-for="page in pdfPages" 
          :key="page.pageNum" 
          class="pdf-page" 
          :ref="el => (page.el = el)" 
        /> 
      </div>
    </div>
  </div>

  <div class="resize-handle"></div>

  <div class="panel">
    <div class="panel-header">📝 研究笔记</div>
    <div class="panel-content">
        <article class="markdown-body" v-html="mdHtml"></article> 
    </div>
  </div>

  <div class="floating-input">
    <input v-model="inputText" placeholder="输入问题或指令…" @keydown.enter.prevent="sendMessage" :disabled="isLoading">
    <button @click="sendMessage" :disabled="isLoading" :class="{ 'loading': isLoading }">
      <span v-if="!isLoading">➤</span>
      <span v-else class="spinner">⟳</span>
    </button>
  </div>

    <div class="right-controls">
      <button @click="importMd">导入MD</button>
      <button @click="exportMd">导出MD</button>
      <button @click="clearMd">清空MD</button>
      <input type="file" ref="mdInput" @change="handleMdSelect" accept=".md" hidden>
    </div>
</template> 
 
 <script setup> 
 import { ref, onMounted, nextTick } from 'vue'
 import axios from 'axios' 
 import { marked } from 'marked' 
 import markedKatex from 'marked-katex-extension' 
 import * as pdfjsLib from 'pdfjs-dist'

 /* ---------- 1. pdf.js 版本对齐 ---------- */ 
 pdfjsLib.GlobalWorkerOptions.workerSrc = '/pdf.worker.min.mjs' 
 marked.use(markedKatex({ throwOnError: false }))
 
 /* ---------- 2. 响应式数据 ---------- */ 
 const inputText  = ref('') 
 const pdfPages   = ref([])   // { pageNum, el}
 const pdfLoaded  = ref(false) 
 const mdHtml     = ref('')
 const chatResponse = ref('') 
 const chatHistory = ref([])  // 存储聊天历史记录
const isLoading = ref(false)  // 加载状态
 const centerEl = ref(null)
 
 /* ---------- 3. PDF渲染相关 ---------- */
 let currentPdf = null; // 保存当前PDF实例

 // 计算最佳渲染参数
 function calculateRenderParams() {
   const containerWidth = centerEl.value?.clientWidth || 800;
   const pixelRatio = window.devicePixelRatio || 1;
   
   return {
     containerWidth: containerWidth - 40, // 减去padding
     pixelRatio,
     qualityMultiplier: Math.max(2.5, pixelRatio * 2) // 提高清晰度倍数
   };
 }

 // 渲染单个PDF页面
 async function renderPdfPage(page, canvas, params) {
   const viewport = page.getViewport({ scale: 1 });
   const scale = params.containerWidth / viewport.width;
   
   // 计算高质量渲染的缩放比例
   const renderScale = scale * params.qualityMultiplier;
   const renderViewport = page.getViewport({ scale: renderScale });
   
   // 设置canvas实际尺寸（高分辨率）
   canvas.width = renderViewport.width;
   canvas.height = renderViewport.height;
   
   // 设置canvas显示尺寸（适应容器）
   canvas.style.width = `${scale * viewport.width}px`;
   canvas.style.height = `${scale * viewport.height}px`;
   canvas.style.maxWidth = '100%';
   canvas.style.display = 'block';
   canvas.style.margin = '0 auto';
   
   const context = canvas.getContext('2d');
   context.clearRect(0, 0, canvas.width, canvas.height);
   
   const renderContext = {
     canvasContext: context,
     viewport: renderViewport,
   };
   
   await page.render(renderContext).promise;
 }

 // 重新渲染所有PDF页面
 async function reRenderPdf() {
   if (!currentPdf || !pdfLoaded.value) return;
   
   const params = calculateRenderParams();
   
   for (const pageObj of pdfPages.value) {
     if (!pageObj.el) continue;
     try {
       const page = await currentPdf.getPage(pageObj.pageNum);
       await renderPdfPage(page, pageObj.el, params);
     } catch (error) {
       console.error(`渲染第${pageObj.pageNum}页失败:`, error);
     }
   }
 }

 // 主PDF渲染函数
 async function renderPdf(arrayBuffer) {
   try {
     if (!arrayBuffer || arrayBuffer.byteLength === 0) {
       throw new Error('PDF文件为空或无效');
     }
     
     const pdfLoadingTask = pdfjsLib.getDocument({
       data: arrayBuffer,
       verbosity: 0
     });
     
     currentPdf = await pdfLoadingTask.promise;
     const params = calculateRenderParams();

     pdfPages.value = Array.from({ length: currentPdf.numPages }, (_, i) => ({
       pageNum: i + 1,
       el: null,
     }));

     await nextTick();

     // 渲染所有页面
     for (const pageObj of pdfPages.value) {
       if (!pageObj.el) continue;
       const page = await currentPdf.getPage(pageObj.pageNum);
       await renderPdfPage(page, pageObj.el, params);
     }
     
   } catch (error) {
     console.error('PDF渲染失败:', error);
     pdfLoaded.value = false;
     currentPdf = null;
     throw new Error(`PDF渲染失败: ${error.message}`);
   }
 }

 const fileInput = ref(null);

 function openFileDialog() {
   fileInput.value.click();
 }

 async function handleFileSelect(event) {
  const file = event.target.files[0];
  if (file && file.type === 'application/pdf') {
    await processFile(file);
  }
}

 async function handleFileDrop(event) {
   const file = event.dataTransfer.files[0]
   if (file && file.type === 'application/pdf') {
     await processFile(file);
   } else {
     alert('请拖放一个 PDF 文件。')
   }
 } 

 async function processFile(file) {
  try {
    // 验证文件大小和类型
    if (file.size > 50 * 1024 * 1024) { // 50MB限制
      throw new Error('PDF文件过大，请选择小于50MB的文件');
    }
    
    if (!file.type.includes('pdf')) {
      throw new Error('请选择有效的PDF文件');
    }

    // 1. 上传并保存到固定路径
    const form = new FormData();
    form.append("file", file);

    const saveRes = await axios.post("/api/save_file", form, {
      headers: { "Content-Type": "multipart/form-data" }
    });

    // 2. 用固定路径触发后端处理
    await axios.post("/api/upload_files");

    // 3. 获取PDF文件并验证
    const response = await axios.get('/demo.pdf', {
      responseType: "arraybuffer"
    });
    
    const arrayBuffer = response.data;
    
    // 验证PDF文件头
    const uint8Array = new Uint8Array(arrayBuffer.slice(0, 4));
    const header = String.fromCharCode(...uint8Array);
    if (header !== '%PDF') {
      throw new Error('文件不是有效的PDF格式');
    }

    // 切换状态，让 canvas 渲染出来
    pdfLoaded.value = true;
    // 等待 DOM 更新
    await nextTick();
    // 渲染 PDF
    await renderPdf(arrayBuffer);

  } catch (error) {
    console.error('文件处理失败:', error);
    let errorMessage = '文件处理失败';
    
    if (error.message.includes('Invalid PDF')) {
      errorMessage = 'PDF文件结构无效，请检查文件是否损坏';
    } else if (error.message.includes('网络')) {
      errorMessage = '网络连接失败，请检查网络连接';
    } else if (error.message) {
      errorMessage = error.message;
    }
    
    alert(errorMessage);
    pdfLoaded.value = false; // 渲染失败，重置状态
  }
} 
 
 /* ---------- 4. Markdown渲染函数 ---------- */
function renderMarkdown(text) {
  if (!text) return '';
  try {
    return marked(text);
  } catch (error) {
    console.error('Markdown渲染失败:', error);
    return text; // 渲染失败时返回原文本
  }
}

/* ---------- 5. 加载 Markdown ---------- */
async function loadMarkdown() {
  try {
    const response = await axios.get('/note.md', {
      responseType: 'text',
      // 避免浏览器缓存
      headers: {
        'Cache-Control': 'no-cache',
      },
    });
    mdHtml.value = marked.parse(response.data);
    await nextTick();
  } catch (error) {
    console.error('加载Markdown文件失败:', error);
    mdHtml.value = marked.parse('# 加载失败\n无法加载Markdown文件，请检查文件路径。');
  }
}

onMounted(() => {
  // 初始加载
  loadMarkdown();

  // 添加窗口大小变化监听器
  let resizeTimeout;
  const handleResize = () => {
    clearTimeout(resizeTimeout);
    resizeTimeout = setTimeout(() => {
      if (pdfLoaded.value) {
        reRenderPdf();
      }
    }, 300); // 防抖，300ms后重新渲染
  };
  
  window.addEventListener('resize', handleResize);

  // 添加页面关闭前的清理操作
  window.addEventListener('beforeunload', () => {
    window.removeEventListener('resize', handleResize);
    // 使用 navigator.sendBeacon 发送一个POST请求
    // 这是一个可靠的方式，可以在页面卸载时发送数据
    navigator.sendBeacon('/api/cleanup', new Blob());
  });
});
 
 const mdInput = ref(null);

function importMd() {
  if (window.confirm('这将覆盖当前的 Markdown 文件，确定要导入吗？')) {
    mdInput.value.click();
  }
}

async function handleMdSelect(event) {
  const file = event.target.files[0];
  if (file) {
    const formData = new FormData();
    formData.append('file', file);
    try {
      await axios.post('/api/import_md', formData, {
        headers: {
          'Content-Type': 'multipart/form-data'
        }
      });
      loadMarkdown(); // 手动刷新
    } catch (error) {
      console.error('导入Markdown文件失败:', error);
      alert('导入失败，请检查文件或网络。');
    }
  }
}

async function exportMd() {
  try {
    const response = await axios.get('/api/export_md', { responseType: 'blob' });
    const blob = new Blob([response.data], { type: 'text/markdown' });
    const url = URL.createObjectURL(blob);
    const a = document.createElement('a');
    a.href = url;
    a.download = 'note.md';
    document.body.appendChild(a);
    a.click();
    document.body.removeChild(a);
    URL.revokeObjectURL(url);
  } catch (error) {
    console.error('导出Markdown文件失败:', error);
    alert('导出失败，请检查网络。');
  }
}

async function clearMd() {
  if (confirm('确定要清空所有Markdown内容吗？此操作不可恢复。')) {
    try {
      await axios.post('/api/clear_md');
      loadMarkdown(); // 手动刷新
    } catch (error) {
      console.error('清空Markdown失败:', error);
      alert('清空失败，请检查网络。');
    }
  }
}



/* ---------- 6. 发送消息到后端 ---------- */
async function sendMessage() {
  if (!inputText.value.trim() || isLoading.value) return;

  isLoading.value = true; // 开始加载
  
  try {
    const rawText = inputText.value.trim(); // 获取原始字符串

    // 发送纯文本的POST请求
    const res = await axios.post('/api/chat', rawText, {
      headers: {
        'Content-Type': 'text/plain' // 明确请求头为纯文本
      }
    });

    // 解析响应数据
    let messageData;
    if (typeof res.data === 'string') {
      try {
        // 尝试解析JSON字符串
        messageData = JSON.parse(res.data);
      } catch {
        // 如果不是JSON，作为普通文本处理
        messageData = { content: res.data, status: '✅ 已生成回复' };
      }
    } else if (typeof res.data === 'object') {
      // 如果已经是对象
      messageData = res.data;
    } else {
      messageData = { content: String(res.data), status: '✅ 已生成回复' };
    }

    // 添加到历史记录
    chatHistory.value.push(messageData);
    
    // 如果有status为updated，刷新markdown
    if (messageData.status === 'updated') {
      loadMarkdown(); // 手动刷新
    }

    inputText.value = ''; // 清空输入框

  } catch (error) {
    console.error('通信错误:', error);

    // 错误处理
    let errorMessage;
    if (error.response) {
      if (typeof error.response.data === 'string') {
        errorMessage = error.response.data;
      } else {
        try {
          errorMessage = error.response.data.detail || JSON.stringify(error.response.data);
        } catch {
          errorMessage = `后端错误：${error.response.status} ${error.response.statusText}`;
        }
      }
    } else if (error.request) {
      errorMessage = '网络错误：请求已发送但未收到响应';
    } else {
      errorMessage = '客户端错误：' + error.message;
    }
    
    // 将错误信息也添加到历史记录
    chatHistory.value.push({ content: errorMessage, status: '❌ 错误' });
  } finally {
    isLoading.value = false; // 结束加载
  }
}
 </script> 
 
 <style scoped> 
 /* ---------- 5. 全局重置 ---------- */ 
 * { 
   margin: 0; 
   padding: 0; 
   box-sizing: border-box; 
 } 
 html, 
 body { 
   height: 100%; 
 } 
 .wrapper { 
   display: flex; 
   height: 100vh; 
 } 
 
 /* ---------- 6. 三栏比例 & 滚动 ---------- */ 
 .left, 
 .center, 
 .right { 
   flex-shrink: 0; 
   overflow-y: auto; 
   /* 隐藏滚动条 WebKit / Firefox */ 
   scrollbar-width: none;      /* Firefox */ 
 } 
 .left::-webkit-scrollbar, 
 .center::-webkit-scrollbar, 
 .right::-webkit-scrollbar { 
   display: none;              /* Chrome / Edge / Safari */ 
 } 
 
 .left  { width: 30%; padding: 20px; }
 .center { width: 40%; padding: 10px; }
 .right  { width: 30%; padding: 20px; position: relative; }

.right-controls {
  position: absolute;
  top: 10px;
  right: 10px;
  display: flex;
  gap: 10px;
}

.right-controls button {
  padding: 5px 10px;
  border: 1px solid #ccc;
  border-radius: 5px;
  background-color: #f0f0f0;
  cursor: pointer;
}
 
 /* 确保markdown样式正确应用 */
 .right :deep(.markdown-body) {
   background-color: transparent !important;
   color: #24292f !important;
   font-size: 14px;
   font-family: -apple-system,BlinkMacSystemFont,"Segoe UI",Helvetica,Arial,sans-serif,"Apple Color Emoji","Segoe UI Emoji" !important;
 }

.drop-zone {
  border: 2px dashed #ccc;
  border-radius: 10px;
  padding: 40px;
  text-align: center;
  cursor: pointer;
  width: 100%;
  height: 100%;
  display: flex;
  flex-direction: column;
  justify-content: center;
  align-items: center;
}

.upload-button {
  margin-top: 15px;
  padding: 10px 20px;
  border: none;
  background-color: #3498db;
  color: white;
  border-radius: 5px;
  cursor: pointer;
}

.page {
  display: block;
  width: 100%;
  margin-bottom: 10px;
  box-shadow: 0 0 4px rgba(0, 0, 0, 0.2);
  background: #fff;
}

.pdf-page {
  margin-bottom: 10px;
  border: 1px solid #ddd;
  box-shadow: 0 2px 8px rgba(0,0,0,0.1);
  display: block;
  max-width: 100%;
  height: auto;
}

.pdf-page-container {
  display: flex;
  flex-direction: column;
  align-items: center;
  padding: 10px;
}

.float-input-wrapper {
  position: fixed;
  bottom: 20px;
  left: 50%;
  transform: translateX(-50%);
  width: 60%;
  display: flex;
}

.float-input {
  flex-grow: 1;
  padding: 15px;
  border-radius: 8px 0 0 8px;
  border: 1px solid #ccc;
  box-shadow: 0 4px 12px rgba(0,0,0,0.15);
  font-size: 16px;
  resize: none;
  z-index: 1000;
}

.send-button {
  padding: 15px 20px;
  border: 1px solid #ccc;
  border-left: none;
  background-color: #3498db;
  color: white;
  border-radius: 0 8px 8px 0;
  cursor: pointer;
  z-index: 1000;
}

.chat-response {
  white-space: pre-wrap; /* or pre-line */
  word-wrap: break-word;
  height: calc(100vh - 120px); /* Adjust based on your layout */
  overflow-y: auto;
}

/* 发送按钮加载状态样式 */
.floating-input button:disabled {
  opacity: 0.6;
  cursor: not-allowed;
}

.floating-input button.loading {
  background: #6366f1;
}

.spinner {
  display: inline-block;
  animation: spin 1s linear infinite;
}

@keyframes spin {
  from { transform: rotate(0deg); }
  to { transform: rotate(360deg); }
}

.floating-input input:disabled {
  opacity: 0.6;
  cursor: not-allowed;
}

/* 左栏消息Markdown样式 */
.message-content {
  line-height: 1.6;
}

.message-content h1, .message-content h2, .message-content h3 {
  margin: 0.5em 0;
  color: #333;
}

.message-content p {
  margin: 0.5em 0;
}

.message-content code {
  background: #f5f5f5;
  padding: 2px 4px;
  border-radius: 3px;
  font-family: 'Courier New', monospace;
}

.message-content pre {
  background: #f5f5f5;
  padding: 10px;
  border-radius: 5px;
  overflow-x: auto;
  margin: 0.5em 0;
}

.message-content ul, .message-content ol {
  margin: 0.5em 0;
  padding-left: 1.5em;
}

.message-content blockquote {
  border-left: 4px solid #ddd;
  margin: 0.5em 0;
  padding-left: 1em;
  color: #666;
}
 </style>