import { AppError } from '../common/errors'

export async function prepareAvatar(file: File): Promise<string> {
  const invalid = (message: string) => new AppError('VALIDATION', message, { fieldErrors: { avatar: message } })
  if (!['image/jpeg', 'image/png', 'image/webp'].includes(file.type)) throw invalid('请选择 JPG、PNG 或 WebP 图片。')
  if (!file.size || file.size > 2 * 1024 * 1024) throw invalid('头像图片不能超过 2 MB。')
  let bitmap: ImageBitmap
  try { bitmap = await createImageBitmap(file) }
  catch { throw invalid('无法读取这张图片，请重新选择。') }
  try {
    if (!bitmap.width || !bitmap.height) throw invalid('无法读取这张图片，请重新选择。')
    const canvas = document.createElement('canvas')
    canvas.width = canvas.height = 256
    const context = canvas.getContext('2d')
    if (!context) throw invalid('无法处理头像图片，请重试。')
    const edge = Math.min(bitmap.width, bitmap.height)
    context.drawImage(bitmap, (bitmap.width - edge) / 2, (bitmap.height - edge) / 2, edge, edge, 0, 0, 256, 256)
    return canvas.toDataURL('image/png')
  } finally { bitmap.close() }
}
