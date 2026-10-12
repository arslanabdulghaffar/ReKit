import '@testing-library/jest-dom/vitest'
import { createRequire } from 'node:module'
import { cleanup, fireEvent } from '@testing-library/react'
import { afterEach } from 'vitest'

const require = createRequire(import.meta.url)
const nativeFileList: { create: (window: Window) => FileList } = require('jsdom/lib/generated/idl/FileList.js')
const bindings: { implForWrapper: (wrapper: object) => unknown } = require('jsdom/lib/generated/idl/utils.js')

/**
 * Emulate the native file picker without replacing input.files or validity.
 * user-event 14.6.7 supplies a wrapper-only FileList, but jsdom 30.1.2 checks its
 * internal selected files for required validation. jsdom has no DataTransfer.
 * These pinned, test-only bindings create a real FileList for the native setter;
 * empty selections still fail required validation and submit uses a real click.
 */
export function selectNativeFiles(input: HTMLInputElement, files: File[]): void {
  if (input.type !== 'file' || input.disabled || (!input.multiple && files.length > 1)) {
    throw new Error('The file control cannot accept this selection.')
  }
  // Vitest rewrites document.defaultView to its test global. Its exposed jsdom
  // instance retains the real window and Web IDL constructor registry.
  const nativeWindow = (globalThis as typeof globalThis & { jsdom: { window: Window } }).jsdom.window
  if (nativeWindow.document !== input.ownerDocument) throw new Error('Expected the active jsdom document.')
  const selected = nativeFileList.create(nativeWindow)
  const selectedItems = bindings.implForWrapper(selected) as unknown[]
  selectedItems.push(...files.map(file => bindings.implForWrapper(file)))
  input.files = selected
  fireEvent.input(input)
  fireEvent.change(input)
}

afterEach(() => {
  cleanup()
})
