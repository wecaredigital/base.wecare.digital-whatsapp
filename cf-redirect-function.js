function handler(event) {
    var request = event.request;
    var uri = request.uri;
    
    // Root path -> redirect to selfservice
    if (uri === '/' || uri === '') {
        return {
            statusCode: 302,
            statusDescription: 'Found',
            headers: { location: { value: 'https://wecare.digital/selfservice' } }
        };
    }
    
    // All other paths -> pass through to S3
    // If file exists in S3, it opens normally
    // If file doesn't exist (404), cf-404-redirect handles it
    return request;
}
