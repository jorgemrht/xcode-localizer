import Foundation
import SheetLocalizer

public protocol SheetGenerator {
    associatedtype Config: SheetConfig
    
    init(config: Config)
    func generate(from csvFilePath: String) async throws
}