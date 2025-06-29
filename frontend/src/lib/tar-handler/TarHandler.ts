export class TarHandler {
  private view: DataView

  constructor(private buffer: ArrayBuffer) {
    this.view = new DataView(buffer)
  }

  private align512(size: number): number {
    const remainder = size % 512
    return remainder ? size + (512 - remainder) : size
  }

  scan(): Map<string, [number, number]> {
    const results = new Map<string, [number, number]>()
    let scanOffset = 0

    while (scanOffset < this.buffer.byteLength) {
      let isZeroBlock = true
      for (let i = 0; i < 512; i++) {
        if (this.view.getUint8(scanOffset + i) !== 0) {
          isZeroBlock = false
          break
        }
      }
      if (isZeroBlock) break

      const nameBytes = new Uint8Array(this.buffer, scanOffset, 100)
      const nullIndex = nameBytes.indexOf(0)
      const strLength = nullIndex !== -1 ? nullIndex : 100
      const name = new TextDecoder('ascii').decode(nameBytes.slice(0, strLength))

      const sizeBytes = new Uint8Array(this.buffer, scanOffset + 124, 12)
      const sizeStr = new TextDecoder('ascii').decode(sizeBytes).trim()
      const size = sizeStr ? parseInt(sizeStr, 8) : 0

      results.set(name.replace(/\0/g, ''), [scanOffset + 512, size])

      scanOffset += 512 + this.align512(size)
    }

    return results
  }
}
