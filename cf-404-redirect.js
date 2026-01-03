function handler(event) {
    var response = event.response;
    var statusCode = response.statusCode;
    
    // 404 or 403 -> redirect to selfservice
    if (statusCode === 404 || statusCode === 403) {
        return {
            statusCode: 302,
            statusDescription: 'Found',
            headers: { location: { value: 'https://wecare.digital/selfservice' } }
        };
    }
    
    return response;
}
