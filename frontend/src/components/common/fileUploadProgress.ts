export type UploadProgress = (phase: 'reading' | 'uploading' | 'saving', loaded?: number, total?: number) => void
export type AttachmentUploader = (file: File, progress: UploadProgress) => Promise<void>
