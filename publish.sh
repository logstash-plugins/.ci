bundle exec rake vendor
echo "---\n:rubygems_api_key: ${GEM_HOST_API_KEY}" > ~/.gem/credentials
chmod 0600 ~/.gem/credentials
bundle exec rake publish_gem
