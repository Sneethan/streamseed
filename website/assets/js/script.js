// Configuration - these should match your .env values
const BUCKET_NAME = 'radio-files';
const VULTR_HOSTNAME = 'sjc1.vultrobjects.com'; // Update this to match your config

async function fetchArchiveFiles() {
    try {
        // Get the container element
        const episodesContainer = document.getElementById('episodes-container');
        if (!episodesContainer) {
            console.error('Episodes container element not found');
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
        episodesContainer.innerHTML = '';

        // Convert contents to array and sort by LastModified date (newest first)
        const sortedContents = Array.from(contents).sort((a, b) => {
            const dateA = new Date(a.getElementsByTagName('LastModified')[0].textContent);
            const dateB = new Date(b.getElementsByTagName('LastModified')[0].textContent);
            return dateB - dateA; // Sort in descending order (newest first)
        });

        // Create elements for each file
        sortedContents.forEach(item => {
            const key = item.getElementsByTagName('Key')[0].textContent;
            
            // Only process MP3 files from the archive folder
            if (key.startsWith('archive/') && key.endsWith('.mp3')) {
                const lastModified = item.getElementsByTagName('LastModified')[0].textContent;
                const fileUrl = `https://${BUCKET_NAME}.${VULTR_HOSTNAME}/${key}`;
                
                // Format the date
                const date = new Date(lastModified);
                const formattedDate = date.toLocaleDateString('en-AU', {
                    year: 'numeric',
                    month: 'long',
                    day: 'numeric'
                });

                // Create card element
                const cardCol = document.createElement('div');
                cardCol.className = 'col-12 mb-4';
                
                // Format the title (remove 'archive/' and '.mp3')
                const title = key.replace('archive/', '').replace('.mp3', '');
                
                // Set the card content
                cardCol.innerHTML = `
                    <div class="card" style="border: 0px;">
                        <div class="card-body d-flex flex-column" style="border-radius: 35px; border: 3px solid var(--bs-primary);">
                            <div class="d-flex justify-content-between align-items-start mb-3">
                                <h4 class="card-title mb-0" style="font-family: 'Helvetica Now Display'; font-weight: 900;">
                                    ${title}
                                </h4>
                                <span class="text-muted" style="font-family: 'Helvetica Now Display';">
                                    ${formattedDate}
                                </span>
                            </div>
                            <audio controls style="width: 100%; border: 3px solid var(--bs-primary); border-radius: 25px;">
                                <source src="${fileUrl}" type="audio/mpeg">
                                Your browser does not support the audio element.
                            </audio>
                        </div>
                    </div>
                `;
                
                episodesContainer.appendChild(cardCol);
            }
        });

    } catch (error) {
        console.error('Error fetching archive files:', error);
        const episodesContainer = document.getElementById('episodes-container');
        if (episodesContainer) {
            episodesContainer.innerHTML = `
                <div class="col-12">
                    <div class="alert alert-danger" role="alert">
                        Failed to load episodes. Please try again later.
                    </div>
                </div>
            `;
        }
    }
}

// Call the function when the page loads
document.addEventListener('DOMContentLoaded', fetchArchiveFiles);
