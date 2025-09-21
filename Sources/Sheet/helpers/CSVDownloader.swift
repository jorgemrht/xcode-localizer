import Foundation
import CoreExtensions
import os.log

public actor CSVDownloader {
    
    private let session: URLSession
    private static let logger = Logger.csvDownloader
    
    public init(timeoutInterval: TimeInterval = 30.0) {
        let config = URLSessionConfiguration.default
        config.timeoutIntervalForRequest = timeoutInterval
        config.timeoutIntervalForResource = timeoutInterval * 2
        config.httpAdditionalHeaders = [
            "User-Agent": "SheetLocalizer/1.0 (Swift 6.2)"
        ]
        config.requestCachePolicy = .reloadIgnoringLocalCacheData
        self.session = URLSession(configuration: config)
        
    }
    
    deinit {
        session.invalidateAndCancel()
    }
    
    public func download(from urlString: String, to outputPath: String) async throws {
        try await validateInputs(urlString: urlString, outputPath: outputPath)
        
        let transformedURL = try GoogleSheetURLTransformer.transformToCSV(urlString.trimmedContent)
        
        guard let url = URL(string: transformedURL) else {
            throw SheetLocalizerError.invalidURL(transformedURL)
        }
        
        
        let (data, response) = try await session.data(from: url)
        
        try validateResponse(response)
        
        try await saveData(data, to: outputPath)
    }
    
    nonisolated private func validateInputs(urlString: String, outputPath: String) async throws {
        guard !urlString.isEmptyOrWhitespace else {
            throw SheetLocalizerError.invalidURL("URL string is empty")
        }
        
        guard !outputPath.isEmptyOrWhitespace else {
            throw SheetLocalizerError.fileSystemError("Output path is empty")
        }
    }
    
    private func validateResponse(_ response: URLResponse) throws {
        guard let httpResponse = response as? HTTPURLResponse else {
            throw SheetLocalizerError.networkError("Invalid HTTP response")
        }
        
        guard 200...299 ~= httpResponse.statusCode else {
            throw SheetLocalizerError.httpError(httpResponse.statusCode)
        }
    }
    
    nonisolated private func saveData(_ data: Data, to outputPath: String) async throws {
        let fileURL = URL(fileURLWithPath: outputPath)
        
        try FileManager.default.createDirectory(
            at: fileURL.deletingLastPathComponent(),
            withIntermediateDirectories: true
        )
        
        try data.write(to: fileURL)
    }
}