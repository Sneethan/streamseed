// Configuration - these should match your .env values
const BUCKET_NAME = 'radio-files';
const VULTR_HOSTNAME = 'sjc1.vultrobjects.com'; // Update this to match your config

async function fetchArchiveFiles() {
    try {
        // Get the container element
        const archiveContainer = document.getElementById('archive-container');
        if (!archiveContainer) {
            console.error('Archive container element not found');
            return;
        }

        // Fetch the files from the bucket
        const response = await fetch(`https://${BUCKET_NAME}.${VULTR_HOSTNAME}/`, {
            method: 'GET',
        });

        if (!response.ok) {
            throw new Error(`HTTP error! status: ${response.status}`);
        }

        // Parse the XML response
        const data = await response.text();
        const parser = new DOMParser();
        const xmlDoc = parser.parseFromString(data, 'text/xml');
        
        // Get all Contents elements (files) from the XML
        const contents = xmlDoc.getElementsByTagName('Contents');
        
        // Clear existing content
        archiveContainer.innerHTML = '';

        // Create elements for each file
        Array.from(contents).forEach(item => {
            const key = item.getElementsByTagName('Key')[0].textContent;
            
            // Only process files from the archive folder
            if (key.startsWith('archive/')) {
                const lastModified = item.getElementsByTagName('LastModified')[0].textContent;
                const size = item.getElementsByTagName('Size')[0].textContent;
                
                // Create card element
                const card = document.createElement('div');
                card.className = 'archive-card';
                
                // Format the date
                const date = new Date(lastModified);
                const formattedDate = date.toLocaleDateString('en-AU', {
                    year: 'numeric',
                    month: 'long',
                    day: 'numeric',
                    hour: '2-digit',
                    minute: '2-digit'
                });

                // Format the size in MB
                const sizeInMB = (parseInt(size) / (1024 * 1024)).toFixed(2);
                
                // Create the download link
                const fileUrl = `https://${BUCKET_NAME}.${VULTR_HOSTNAME}/${key}`;
                
                // Set the card content
                card.innerHTML = `
                    <h3>${key.replace('archive/', '')}</h3>
                    <p>Recorded: ${formattedDate}</p>
                    <p>Size: ${sizeInMB} MB</p>
                    <a href="${fileUrl}" download class="download-button">
                        Download Recording
                    </a>
                `;
                
                archiveContainer.appendChild(card);
            }
        });

    } catch (error) {
        console.error('Error fetching archive files:', error);
        const archiveContainer = document.getElementById('archive-container');
        if (archiveContainer) {
            archiveContainer.innerHTML = `
                <div class="error-message">
                    Failed to load archive files. Please try again later.
                </div>
            `;
        }
    }
}

// Add some basic styles
const styles = `
    .archive-card {
        border: 1px solid #ddd;
        border-radius: 8px;
        padding: 16px;
        margin: 16px;
        background-color: #fff;
        box-shadow: 0 2px 4px rgba(0,0,0,0.1);
    }

    .archive-card h3 {
        margin: 0 0 8px 0;
        color: #333;
    }

    .archive-card p {
        margin: 4px 0;
        color: #666;
    }

    .download-button {
        display: inline-block;
        background-color: #007bff;
        color: white;
        padding: 8px 16px;
        border-radius: 4px;
        text-decoration: none;
        margin-top: 8px;
    }

    .download-button:hover {
        background-color: #0056b3;
    }

    .error-message {
        color: #dc3545;
        padding: 16px;
        text-align: center;
    }
`;

// Add styles to the document
const styleSheet = document.createElement('style');
styleSheet.textContent = styles;
document.head.appendChild(styleSheet);

// Call the function when the page loads
document.addEventListener('DOMContentLoaded', fetchArchiveFiles);
