If you do not have DBeaver, you can download it from its [website](https://dbeaver.io/download/).

    
        
            Create a new database connection
        </StepHikeCompact.Details>

        
            ![new database connection](/docs/img/guides/database/connecting-to-postgres/dbeaver/new_database_connection.png)
        </StepHikeCompact.Code>

  </StepHikeCompact.Step>

  
    

    
                    ![Selection Menu](/docs/img/guides/database/connecting-to-postgres/dbeaver/select_postgres.png)

    </StepHikeCompact.Code>

  </StepHikeCompact.Step>

  
    
      On your project dashboard, click [Connect](/dashboard/project/_?showConnect=true), note your session pooler's:
      - host
      - username

      You will also need your database's password. If you forgot it, you can generate a new one in the settings.
      

        If you're in an [IPv6 environment](https://github.com/orgs/supabase/discussions/27034) or have the IPv4 Add-On, you can use the direct connection string instead of Supavisor in Session mode.

      

    </StepHikeCompact.Details>

    
        ![database credentials](/docs/img/guides/database/connecting-to-postgres/dbeaver/session_mode.png)
    </StepHikeCompact.Code>

  </StepHikeCompact.Step>

  
    
        In DBeaver's Main menu, add your host, username, and password
    </StepHikeCompact.Details>

    
                ![filling out form](/docs/img/guides/database/connecting-to-postgres/dbeaver/filling_credentials.png)
    </StepHikeCompact.Code>

  </StepHikeCompact.Step>

  
    
        In the [Database Settings](/dashboard/project/_/database/settings), download your SSL certificate.
    </StepHikeCompact.Details>

    
        ![filling out form](/docs/img/guides/database/connecting-to-postgres/dbeaver/certificate.png)
    </StepHikeCompact.Code>

  </StepHikeCompact.Step>

    
    
        In DBeaver's SSL tab, add your SSL certificate
    </StepHikeCompact.Details>

    
        ![filling out form](/docs/img/guides/database/connecting-to-postgres/dbeaver/ssl_tab.png)
    </StepHikeCompact.Code>

  </StepHikeCompact.Step>

      
    
        Test your connection and then click finish. You should now be able to interact with your database with DBeaver
    </StepHikeCompact.Details>

    
        ![connected dashboard](/docs/img/guides/database/connecting-to-postgres/dbeaver/finished.png)
    </StepHikeCompact.Code>

  </StepHikeCompact.Step>