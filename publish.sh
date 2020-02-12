bundle exec rake vendor
mkdir -p ~/.gem
echo "---" > ~/.gem/credentials
echo ":rubygems_api_key: ${GEM_HOST_API_KEY}" >> ~/.gem/credentials
chmod 0600 ~/.gem/credentials
bundle exec rake publish_gem
