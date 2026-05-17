import React, { useState, useRef, useEffect } from 'react';
import { Button } from './components/ui/button';
import { Input } from './components/ui/input';
import { Textarea } from './components/ui/textarea';
import { Card, CardContent, CardHeader, CardTitle, CardDescription } from './components/ui/card';
import { Upload, Send, FileText, Bot, User, Info, AlertCircle, Loader2 } from 'lucide-react';
import Compare from './pages/Compare';

const API_BASE_URL = 'http://localhost:8000/api/v1';

function App() {
  // 'compare' is the hackathon dashboard; 'chat' is a legacy pre-hackathon view kept for reference.
  // eslint-disable-next-line no-unused-vars
  const [view, setView] = useState('compare');
  const [messages, setMessages] = useState([]);
  const [inputMessage, setInputMessage] = useState('');
  const [isLoading, setIsLoading] = useState(false);
  const [file, setFile] = useState(null);
  const [isProcessing, setIsProcessing] = useState(false);
  const [uploadStatus, setUploadStatus] = useState('');
  const [currentDocument, setCurrentDocument] = useState(null);
  const [suggestedQuestions, setSuggestedQuestions] = useState([]);
  const messagesEndRef = useRef(null);
  const fileInputRef = useRef(null);

  const scrollToBottom = () => {
    messagesEndRef.current?.scrollIntoView({ behavior: "smooth" });
  };

  useEffect(() => {
    scrollToBottom();
  }, [messages]);

  const handleFileChange = (e) => {
    const selectedFile = e.target.files[0];
    if (selectedFile) {
      setFile(selectedFile);
      setUploadStatus('');
    }
  };

  const handleFileUpload = async () => {
    if (!file) {
      setUploadStatus('Please select a file first');
      return;
    }

    setIsProcessing(true);
    setUploadStatus('Processing document...');

    const formData = new FormData();
    formData.append('file', file);

    try {
      const response = await fetch(`${API_BASE_URL}/process`, {
        method: 'POST',
        body: formData,
      });

      if (!response.ok) {
        const errorData = await response.json().catch(() => ({ detail: 'Upload failed' }));
        throw new Error(errorData.detail || `Upload failed with status ${response.status}`);
      }

      const data = await response.json();
      setUploadStatus(`✓ Success! Document processed and ready for questions`);
      setFile(null);
      if (fileInputRef.current) {
        fileInputRef.current.value = '';
      }

      // Smart reset: only clear chat if document is NOT similar to previous ones
      if (data.similar_to_previous) {
        // Keep existing chat, just switch current document
        setCurrentDocument(data.file.original_name);
        setMessages(prev => [...prev, {
          role: 'system',
          content: `Added "${data.file.original_name}" - similar to previous documents. Previous context maintained. You can reference both documents.`
        }]);
      } else {
        // Clear previous chat for unrelated document
        setMessages([]);
        setSuggestedQuestions([]);
        setCurrentDocument(data.file.original_name);
        setMessages([{
          role: 'system',
          content: `Now chatting with "${data.file.original_name}". Ask me anything about this document!`
        }]);
      }
    } catch (error) {
      console.error('Upload error:', error);
      setUploadStatus(`✗ Error: ${error.message}`);
    } finally {
      setIsProcessing(false);
    }
  };

  const handleSendMessage = async () => {
    if (!inputMessage.trim() || isLoading) return;

    const userMessage = inputMessage;
    setInputMessage('');

    // Add user message
    setMessages(prev => [...prev, { role: 'user', content: userMessage }]);
    setIsLoading(true);

    try {
      const response = await fetch(`${API_BASE_URL}/chat/message`, {
        method: 'POST',
        headers: {
          'Content-Type': 'application/json',
        },
        body: JSON.stringify({
          message: userMessage,
          use_context: true,
          max_context_chunks: 3,
          document_filter: currentDocument  // Filter by current document
        }),
      });

      if (!response.ok) {
        throw new Error('Failed to get response');
      }

      const data = await response.json();

      // Add AI response
      setMessages(prev => [...prev, {
        role: 'assistant',
        content: data.response,
        metadata: data.metadata
      }]);

      // Set suggested questions if provided
      if (data.suggested_questions && data.suggested_questions.length > 0) {
        setSuggestedQuestions(data.suggested_questions);
      }
    } catch (error) {
      setMessages(prev => [...prev, {
        role: 'error',
        content: `Error: ${error.message}`
      }]);
    } finally {
      setIsLoading(false);
    }
  };

  const handleKeyPress = (e) => {
    if (e.key === 'Enter' && !e.shiftKey) {
      e.preventDefault();
      handleSendMessage();
    }
  };

  return (
    <div className="min-h-screen w-full p-4 md:p-8">
      <div className="max-w-6xl mx-auto space-y-6">
        {/* Header */}
        <div className="text-center space-y-1 py-5">
          <h1 className="text-2xl md:text-3xl font-bold bg-gradient-to-r from-rust-400 via-rust-500 to-rust-600 bg-clip-text text-transparent">
            Token Comparison Across Three RAG Pipelines
          </h1>
          <p className="text-metal-400 text-xs md:text-sm">
            LLM-Only · Basic RAG · GraphRAG (TigerGraph) · full methodology in the README
          </p>
        </div>

        {view === 'compare' ? (
          <Compare />
        ) : (
        <>
        {/* File Upload Section */}
        <Card className="border-metal-600 shadow-2xl">
          <CardHeader>
            <CardTitle className="flex items-center gap-2">
              <Upload className="w-6 h-6 text-rust-500" />
              Upload Document
            </CardTitle>
            <CardDescription>
              Upload PDF, TXT, MD, or code files to start analyzing
            </CardDescription>
          </CardHeader>
          <CardContent>
            <div className="flex flex-col items-center justify-center gap-4 py-2">
              <div className="w-full max-w-lg px-4">
                <Input
                  ref={fileInputRef}
                  type="file"
                  onChange={handleFileChange}
                  accept=".pdf,.txt,.md,.py,.js,.ts,.java,.c,.cpp,.html,.css,.json,.yaml,.yml"
                  disabled={isProcessing}
                  className="w-full h-14 cursor-pointer file:cursor-pointer file:mr-4 file:py-2 file:px-4 file:rounded-md file:border-0 file:text-sm file:font-medium file:bg-rust-500 file:text-white hover:file:bg-rust-600 transition-colors"
                />
              </div>
              <Button
                onClick={handleFileUpload}
                disabled={!file || isProcessing}
                size="sm"
                className="w-32"
              >
                {isProcessing ? (
                  <>
                    <Loader2 className="w-4 h-4 animate-spin mr-2" />
                    Processing...
                  </>
                ) : (
                  <>
                    <Upload className="w-4 h-4 mr-2" />
                    Upload
                  </>
                )}
              </Button>
            </div>
            {uploadStatus && (
              <div className={`flex items-center gap-2 p-3 rounded-md text-sm ${
                uploadStatus.includes('✓')
                  ? 'bg-green-900/20 border border-green-700 text-green-400'
                  : uploadStatus.includes('✗')
                  ? 'bg-red-900/20 border border-red-700 text-red-400'
                  : 'bg-blue-900/20 border border-blue-700 text-blue-400'
              }`}>
                {uploadStatus.includes('✓') && <FileText className="w-4 h-4" />}
                {uploadStatus.includes('✗') && <AlertCircle className="w-4 h-4" />}
                {!uploadStatus.includes('✓') && !uploadStatus.includes('✗') && <Loader2 className="w-4 h-4 animate-spin" />}
                {uploadStatus}
              </div>
            )}
          </CardContent>
        </Card>

        {/* Chat Section */}
        <Card className="border-metal-600 shadow-2xl min-h-[600px] flex flex-col">
          <CardHeader className="pb-4">
            <CardTitle className="flex items-center gap-2">
              <Bot className="w-6 h-6 text-rust-500" />
              AI Assistant
            </CardTitle>
          </CardHeader>
          <CardContent className="flex-1 flex flex-col p-0">
            {/* Messages */}
            <div className="flex-1 overflow-y-auto p-6 space-y-4 min-h-[400px] max-h-[500px]">
              {messages.length === 0 ? (
                <div className="flex flex-col items-center justify-center h-full text-center space-y-6 py-12">
                  <div className="w-20 h-20 rounded-full bg-metal-gradient flex items-center justify-center shadow-lg">
                    <Bot className="w-10 h-10 text-rust-400" />
                  </div>
                  <div className="space-y-2">
                    <h2 className="text-2xl font-semibold text-rust-400">Welcome</h2>
                    <p className="text-metal-400 max-w-md">Upload a document above to get started, then ask questions about it.</p>
                  </div>
                  <div className="grid grid-cols-1 md:grid-cols-2 gap-3 max-w-2xl">
                    <div className="flex items-start gap-3 p-4 bg-steel-800/50 rounded-lg border border-metal-700">
                      <FileText className="w-5 h-5 text-rust-500 flex-shrink-0 mt-0.5" />
                      <div className="text-left">
                        <div className="font-medium text-metal-200">Upload Documents</div>
                        <div className="text-sm text-metal-400">PDF, TXT, MD, code files</div>
                      </div>
                    </div>
                    <div className="flex items-start gap-3 p-4 bg-steel-800/50 rounded-lg border border-metal-700">
                      <svg className="w-5 h-5 text-rust-500 flex-shrink-0 mt-0.5" fill="none" viewBox="0 0 24 24" stroke="currentColor">
                        <path strokeLinecap="round" strokeLinejoin="round" strokeWidth={2} d="M21 21l-6-6m2-5a7 7 0 11-14 0 7 7 0 0114 0z" />
                      </svg>
                      <div className="text-left">
                        <div className="font-medium text-metal-200">Intelligent Search</div>
                        <div className="text-sm text-metal-400">Semantic similarity search</div>
                      </div>
                    </div>
                    <div className="flex items-start gap-3 p-4 bg-steel-800/50 rounded-lg border border-metal-700">
                      <Bot className="w-5 h-5 text-rust-500 flex-shrink-0 mt-0.5" />
                      <div className="text-left">
                        <div className="font-medium text-metal-200">AI Responses</div>
                        <div className="text-sm text-metal-400">Powered by Google Gemini</div>
                      </div>
                    </div>
                    <div className="flex items-start gap-3 p-4 bg-steel-800/50 rounded-lg border border-metal-700">
                      <svg className="w-5 h-5 text-rust-500 flex-shrink-0 mt-0.5" fill="none" viewBox="0 0 24 24" stroke="currentColor">
                        <path strokeLinecap="round" strokeLinejoin="round" strokeWidth={2} d="M9 12l2 2 4-4m6 2a9 9 0 11-18 0 9 9 0 0118 0z" />
                      </svg>
                      <div className="text-left">
                        <div className="font-medium text-metal-200">Context-Aware</div>
                        <div className="text-sm text-metal-400">Answers from your documents</div>
                      </div>
                    </div>
                  </div>
                </div>
              ) : (
                <>
                  {messages.map((msg, index) => (
                    <div key={index} className={`flex gap-3 ${msg.role === 'user' ? 'justify-end' : 'justify-start'}`}>
                      {msg.role !== 'user' && (
                        <div className={`w-8 h-8 rounded-full flex items-center justify-center flex-shrink-0 ${
                          msg.role === 'assistant' ? 'bg-rust-gradient' :
                          msg.role === 'system' ? 'bg-blue-600' :
                          'bg-red-600'
                        }`}>
                          {msg.role === 'assistant' && <Bot className="w-5 h-5 text-white" />}
                          {msg.role === 'system' && <Info className="w-5 h-5 text-white" />}
                          {msg.role === 'error' && <AlertCircle className="w-5 h-5 text-white" />}
                        </div>
                      )}
                      <div className={`max-w-[80%] ${msg.role === 'user' ? 'order-first' : ''}`}>
                        <div className={`rounded-lg p-4 ${
                          msg.role === 'user'
                            ? 'bg-metal-gradient text-white shadow-lg'
                            : msg.role === 'assistant'
                            ? 'bg-steel-800 text-metal-100 border border-metal-700 shadow-lg'
                            : msg.role === 'system'
                            ? 'bg-blue-900/20 text-blue-300 border border-blue-700'
                            : 'bg-red-900/20 text-red-300 border border-red-700'
                        }`}>
                          <div className="whitespace-pre-wrap break-words">{msg.content}</div>
                          {msg.metadata && (
                            <div className="mt-3 pt-3 border-t border-metal-600 text-xs text-metal-400 space-y-1">
                              {msg.metadata.model && <div>Model: {msg.metadata.model}</div>}
                              {msg.metadata.context_chunks_used > 0 && (
                                <div className="flex items-center gap-1">
                                  <FileText className="w-3 h-3" />
                                  Based on uploaded documents
                                </div>
                              )}
                            </div>
                          )}
                        </div>
                      </div>
                      {msg.role === 'user' && (
                        <div className="w-8 h-8 rounded-full bg-metal-gradient flex items-center justify-center flex-shrink-0">
                          <User className="w-5 h-5 text-white" />
                        </div>
                      )}
                    </div>
                  ))}
                  {isLoading && (
                    <div className="flex gap-3 justify-start">
                      <div className="w-8 h-8 rounded-full bg-rust-gradient flex items-center justify-center flex-shrink-0">
                        <Bot className="w-5 h-5 text-white" />
                      </div>
                      <div className="bg-steel-800 text-metal-100 border border-metal-700 shadow-lg rounded-lg p-4">
                        <div className="flex gap-1">
                          <span className="w-2 h-2 bg-rust-500 rounded-full typing-dot"></span>
                          <span className="w-2 h-2 bg-rust-500 rounded-full typing-dot"></span>
                          <span className="w-2 h-2 bg-rust-500 rounded-full typing-dot"></span>
                        </div>
                      </div>
                    </div>
                  )}
                </>
              )}
              <div ref={messagesEndRef} />
            </div>

            {/* Input Section */}
            <div className="p-6 border-t border-metal-700 bg-steel-900/50">
              {/* Suggested Questions */}
              {suggestedQuestions.length > 0 && (
                <div className="mb-4">
                  <p className="text-sm text-metal-400 mb-2">Suggested questions:</p>
                  <div className="flex flex-wrap gap-2">
                    {suggestedQuestions.map((question, index) => (
                      <button
                        key={index}
                        onClick={() => {
                          setInputMessage(question);
                          setSuggestedQuestions([]);
                        }}
                        className="px-3 py-2 text-sm bg-steel-800 hover:bg-steel-700 text-metal-200 rounded-lg border border-metal-600 transition-colors"
                      >
                        {question}
                      </button>
                    ))}
                  </div>
                </div>
              )}

              <div className="flex gap-3">
                <Textarea
                  value={inputMessage}
                  onChange={(e) => setInputMessage(e.target.value)}
                  onKeyPress={handleKeyPress}
                  placeholder={currentDocument ? `Ask about ${currentDocument}...` : "Upload a document to get started..."}
                  disabled={isLoading}
                  rows={3}
                  className="flex-1"
                />
                <Button
                  onClick={handleSendMessage}
                  disabled={!inputMessage.trim() || isLoading}
                  size="lg"
                  className="h-auto px-6"
                >
                  {isLoading ? (
                    <Loader2 className="w-5 h-5 animate-spin" />
                  ) : (
                    <>
                      <Send className="w-5 h-5" />
                      Send
                    </>
                  )}
                </Button>
              </div>
            </div>
          </CardContent>
        </Card>
        </>
        )}
      </div>
    </div>
  );
}

export default App;
