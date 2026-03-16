import type { Drawing } from '../types'
import { BaseDrawingPlugin } from './base-drawing'
import { HorizontalLinePlugin } from './hline'
import { VerticalLinePlugin } from './vline'
import { TrendlinePlugin } from './trendline'
import { ChannelPlugin } from './channel'
import { RectanglePlugin } from './rectangle'
import { FibRetracementPlugin } from './fib-retracement'
import { MeasurePlugin } from './measure'

export function createDrawingPlugin(drawing: Drawing): BaseDrawingPlugin {
  switch (drawing.type) {
    case 'hline':     return new HorizontalLinePlugin(drawing)
    case 'vline':     return new VerticalLinePlugin(drawing)
    case 'trendline': return new TrendlinePlugin(drawing)
    case 'channel':   return new ChannelPlugin(drawing)
    case 'rectangle': return new RectanglePlugin(drawing)
    case 'fib':       return new FibRetracementPlugin(drawing)
    case 'measure':   return new MeasurePlugin(drawing)
    default: {
      const _exhaustive: never = drawing.type
      throw new Error(`Unknown drawing type: ${_exhaustive}`)
    }
  }
}

export { BaseDrawingPlugin } from './base-drawing'
export { HorizontalLinePlugin } from './hline'
export { VerticalLinePlugin } from './vline'
export { TrendlinePlugin } from './trendline'
export { ChannelPlugin } from './channel'
export { RectanglePlugin } from './rectangle'
export { FibRetracementPlugin } from './fib-retracement'
export { MeasurePlugin } from './measure'
